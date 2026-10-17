import "dotenv/config";

function required(name) {
  const value = process.env[name];
  if (typeof value !== "string" || value.trim() === "") {
    throw new Error(`Falta la variable de entorno ${name}`);
  }
  return value.trim();
}

function phoneNumberId() {
  const primary = process.env.PHONE_NUMBER_ID;
  const fallback = process.env.WHATSAPP_PHONE_NUMBER_ID;
  const value = (primary || fallback || "").trim();
  if (!/^[0-9]{5,20}$/.test(value)) {
    throw new Error("PHONE_NUMBER_ID debe ser el identificador numérico de Meta");
  }
  return value;
}

const port = Number(process.env.PORT || 3000);
if (!Number.isInteger(port) || port < 1 || port > 65535) {
  throw new Error("PORT debe ser un entero entre 1 y 65535");
}

const graphVersion = (process.env.WHATSAPP_GRAPH_VERSION || "v21.0").trim();
if (!/^v\d+\.\d+$/.test(graphVersion)) {
  throw new Error("WHATSAPP_GRAPH_VERSION debe tener la forma v21.0");
}

export const config = {
  port,
  token: required("WHATSAPP_TOKEN"),
  phoneNumberId: phoneNumberId(),
  verifyToken: required("WHATSAPP_VERIFY_TOKEN"),
  appSecret: (process.env.WHATSAPP_APP_SECRET || "").trim(),
  graphVersion,
};
