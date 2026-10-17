import express from "express";

import { config } from "./config.js";
import { webhookRouter } from "./routes/webhook.js";

const app = express();

app.disable("x-powered-by");

app.use(
  express.json({
    limit: "1mb",
    verify(req, _res, buffer) {
      req.rawBody = buffer;
    },
  }),
);

app.get("/health", (_req, res) => {
  res.status(200).json({ ok: true });
});

app.use("/webhook", webhookRouter);

app.use((error, _req, res, _next) => {
  if (error instanceof SyntaxError && error.status === 400) {
    res.status(400).json({ error: "invalid json" });
    return;
  }
  console.error("Error no controlado:", error.message);
  res.status(500).json({ error: "internal error" });
});

app.listen(config.port, () => {
  const signature = config.appSecret ? "activa" : "pendiente";
  console.log(
    `WhatsApp webhook en el puerto ${config.port} (${config.graphVersion}, firma ${signature})`,
  );
});
