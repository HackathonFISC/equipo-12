"""Deterministic cistern routing with OR-Tools.

Demand, speed, service time, the depot and the default fleet are ASSUMPTION
demo values. They are not an IDAAN fleet, a surveyed yard, or official policy.
The numeric route comes from the solver, not from a language model.
"""

from __future__ import annotations

from dataclasses import dataclass

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from src.contracts import Assignment, NormalizedIncidentCluster, PriorityResult
from src.ingestion.geolocator import haversine_meters

# ASSUMPTION: 15 liters per affected person fits one 7 000 L truck for 400
# people and does not fit two such stops on that same truck.
LITERS_PER_PERSON = 15
SERVICE_MINUTES = 20
SPEED_KMH = 30
DEPOT_LATITUDE = 8.881
DEPOT_LONGITUDE = -79.782
_RANK_COST = 1_000


@dataclass(frozen=True)
class Truck:
    vehicle_id: str
    capacity_liters: int
    shift_minutes: int


@dataclass(frozen=True)
class SolveResult:
    assignments: list[Assignment]
    route_order: list[str]
    unserved: list[str]
    constraints: list[str]


DEFAULT_FLEET: tuple[Truck, ...] = (
    Truck("cisterna-1", 10_000, 480),
    Truck("cisterna-2", 10_000, 480),
    Truck("cisterna-3", 8_000, 480),
)


@dataclass(frozen=True)
class _Stop:
    cluster: NormalizedIncidentCluster
    score: float
    demand: int
    depot_minutes: int
    rank: int


def solve(
    clusters: list[NormalizedIncidentCluster],
    scores: list[PriorityResult],
    fleet: list[Truck] | None = None,
) -> SolveResult:
    """Assign stops to trucks. Higher score is visited earlier when both fit."""
    trucks = tuple(sorted(fleet if fleet is not None else DEFAULT_FLEET, key=lambda item: item.vehicle_id))
    score_by_id = {item.cluster_id: item.score for item in scores}
    unserved: list[str] = []
    candidates: list[_Stop] = []
    for cluster in clusters:
        reason = _reject_reason(cluster, score_by_id.get(cluster.cluster_id, 0.0), trucks)
        if reason is not None:
            unserved.append(cluster.sector_id.value)
            continue
        latitude = cluster.latitude
        longitude = cluster.longitude
        assert latitude is not None and longitude is not None
        affected = cluster.estimated_affected_count
        assert affected is not None
        candidates.append(
            _Stop(
                cluster=cluster,
                score=score_by_id.get(cluster.cluster_id, 0.0),
                demand=affected * LITERS_PER_PERSON,
                depot_minutes=_travel_minutes(DEPOT_LATITUDE, DEPOT_LONGITUDE, latitude, longitude),
                rank=0,
            )
        )
    ordered = sorted(candidates, key=lambda item: (-item.score, item.cluster.cluster_id))
    stops = [
        _Stop(
            cluster=item.cluster,
            score=item.score,
            demand=item.demand,
            depot_minutes=item.depot_minutes,
            rank=index,
        )
        for index, item in enumerate(ordered)
    ]
    if not stops or not trucks:
        return SolveResult([], [], unserved, ["capacity", "shift-window"])
    routed, dropped, used_ortools = _route_with_ortools(stops, trucks)
    unserved.extend(item.cluster.sector_id.value for item in dropped)
    constraints = ["capacity", "shift-window"]
    if used_ortools:
        constraints.append("ortools-routing")
    return SolveResult(
        assignments=routed,
        route_order=[item.sector_id.value for item in routed],
        unserved=unserved,
        constraints=constraints,
    )


def _reject_reason(
    cluster: NormalizedIncidentCluster,
    score: float,
    trucks: tuple[Truck, ...],
) -> str | None:
    del score
    if not trucks:
        return "no-fleet"
    if cluster.latitude is None or cluster.longitude is None:
        return "no-coordinates"
    affected = cluster.estimated_affected_count
    if affected is None or affected <= 0:
        return "no-demand"
    demand = affected * LITERS_PER_PERSON
    depot_minutes = _travel_minutes(
        DEPOT_LATITUDE,
        DEPOT_LONGITUDE,
        cluster.latitude,
        cluster.longitude,
    )
    tour = depot_minutes + SERVICE_MINUTES + depot_minutes
    if any(demand <= truck.capacity_liters and tour <= truck.shift_minutes for truck in trucks):
        return None
    return "infeasible"


def _travel_minutes(latitude_a: float, longitude_a: float, latitude_b: float, longitude_b: float) -> int:
    meters = haversine_meters(latitude_a, longitude_a, latitude_b, longitude_b)
    minutes = (meters / 1000.0) / SPEED_KMH * 60.0
    if minutes <= 0:
        return 0
    return int(round(minutes))


def _route_with_ortools(
    stops: list[_Stop],
    trucks: tuple[Truck, ...],
) -> tuple[list[Assignment], list[_Stop], bool]:
    count = len(stops) + 1
    manager = pywrapcp.RoutingIndexManager(count, len(trucks), 0)
    routing = pywrapcp.RoutingModel(manager)
    matrix = _time_matrix(stops)

    def transit(from_index: int, to_index: int) -> int:
        origin = manager.IndexToNode(from_index)
        destination = manager.IndexToNode(to_index)
        service = 0 if origin == 0 else SERVICE_MINUTES
        return matrix[origin][destination] + service

    def cost(from_index: int, to_index: int) -> int:
        destination = manager.IndexToNode(to_index)
        origin = manager.IndexToNode(from_index)
        travel = matrix[origin][destination]
        if destination == 0:
            return travel
        return travel + stops[destination - 1].rank * _RANK_COST

    def demand(from_index: int) -> int:
        node = manager.IndexToNode(from_index)
        if node == 0:
            return 0
        return stops[node - 1].demand

    transit_index = routing.RegisterTransitCallback(transit)
    cost_index = routing.RegisterTransitCallback(cost)
    routing.SetArcCostEvaluatorOfAllVehicles(cost_index)
    horizon = max(truck.shift_minutes for truck in trucks)
    routing.AddDimension(transit_index, horizon, horizon, True, "Time")
    time_dimension = routing.GetDimensionOrDie("Time")
    demand_index = routing.RegisterUnaryTransitCallback(demand)
    routing.AddDimensionWithVehicleCapacity(
        demand_index,
        0,
        [truck.capacity_liters for truck in trucks],
        True,
        "Capacity",
    )
    for vehicle, truck in enumerate(trucks):
        time_dimension.CumulVar(routing.End(vehicle)).SetMax(truck.shift_minutes)
    for node, stop in enumerate(stops, start=1):
        penalty = 1_000_000 + (len(stops) - stop.rank) * 100_000
        routing.AddDisjunction([manager.NodeToIndex(node)], penalty)

    parameters = pywrapcp.DefaultRoutingSearchParameters()
    parameters.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    parameters.solution_limit = 1
    parameters.time_limit.seconds = 1
    solution = routing.SolveWithParameters(parameters)
    if solution is None:
        routed, dropped = _greedy(stops, trucks)
        return routed, dropped, False
    assignments: list[Assignment] = []
    visited: set[int] = set()
    for vehicle, truck in enumerate(trucks):
        index = routing.Start(vehicle)
        order = 1
        while not routing.IsEnd(index):
            node = manager.IndexToNode(index)
            if node != 0:
                stop = stops[node - 1]
                visited.add(node)
                assignments.append(
                    Assignment(
                        vehicle_id=truck.vehicle_id,
                        sector_id=stop.cluster.sector_id,
                        order=order,
                        volume_liters=stop.demand,
                    )
                )
                order += 1
            index = solution.Value(routing.NextVar(index))
    dropped = [stop for node, stop in enumerate(stops, start=1) if node not in visited]
    return assignments, dropped, True


def _greedy(stops: list[_Stop], trucks: tuple[Truck, ...]) -> tuple[list[Assignment], list[_Stop]]:
    remaining = {truck.vehicle_id: truck.capacity_liters for truck in trucks}
    clock = {truck.vehicle_id: 0 for truck in trucks}
    position = {truck.vehicle_id: (DEPOT_LATITUDE, DEPOT_LONGITUDE) for truck in trucks}
    next_order = {truck.vehicle_id: 1 for truck in trucks}
    assignments: list[Assignment] = []
    dropped: list[_Stop] = []
    for stop in stops:
        latitude = stop.cluster.latitude
        longitude = stop.cluster.longitude
        assert latitude is not None and longitude is not None
        feasible: list[tuple[int, str]] = []
        for truck in trucks:
            if stop.demand > remaining[truck.vehicle_id]:
                continue
            origin_lat, origin_lon = position[truck.vehicle_id]
            travel = _travel_minutes(origin_lat, origin_lon, latitude, longitude)
            arrival = clock[truck.vehicle_id] + travel
            back = _travel_minutes(latitude, longitude, DEPOT_LATITUDE, DEPOT_LONGITUDE)
            if arrival + SERVICE_MINUTES + back > truck.shift_minutes:
                continue
            feasible.append((arrival, truck.vehicle_id))
        if not feasible:
            dropped.append(stop)
            continue
        _, vehicle_id = min(feasible)
        origin_lat, origin_lon = position[vehicle_id]
        travel = _travel_minutes(origin_lat, origin_lon, latitude, longitude)
        remaining[vehicle_id] -= stop.demand
        clock[vehicle_id] = clock[vehicle_id] + travel + SERVICE_MINUTES
        position[vehicle_id] = (latitude, longitude)
        assignments.append(
            Assignment(
                vehicle_id=vehicle_id,
                sector_id=stop.cluster.sector_id,
                order=next_order[vehicle_id],
                volume_liters=stop.demand,
            )
        )
        next_order[vehicle_id] += 1
    return assignments, dropped


def _time_matrix(stops: list[_Stop]) -> list[list[int]]:
    points: list[tuple[float, float]] = [(DEPOT_LATITUDE, DEPOT_LONGITUDE)]
    for stop in stops:
        latitude = stop.cluster.latitude
        longitude = stop.cluster.longitude
        assert latitude is not None and longitude is not None
        points.append((latitude, longitude))
    matrix: list[list[int]] = []
    for origin in points:
        row = [
            _travel_minutes(origin[0], origin[1], destination[0], destination[1])
            for destination in points
        ]
        matrix.append(row)
    return matrix
