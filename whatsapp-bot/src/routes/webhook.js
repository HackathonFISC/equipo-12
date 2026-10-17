import { Router } from "express";

import { config } from "../config.js";
import { verifyMetaSignature } from "../middleware/verifySignature.js";
import { handleConversation } from "../services/conversation.js";
import { sendTextMessage } from "../services/whatsapp.js";

export const webhookRouter = Router();

const seenMessageIds = new Set();
const maxSeenIds = 1000;
let warnedAboutSignature = false;

function alreadyHandled(messageId) {
  if (!messageId) {
    return false;
  }
  if (seenMessageIds.has(messageId)) {
    return true;
  }
  seenMessageIds.add(messageId);
  if (seenMessageIds.size > maxSeenIds) {
    const oldest = seenMessageIds.values().next().value;
    seenMessageIds.delete(oldest);
  }
  return false;
}

function extractTextMessages(payload) {
  if (!payload || payload.object !== "whatsapp_business_account" || !Array.isArray(payload.entry)) {
    return [];
  }
  const messages = [];
  for (const entry of payload.entry) {
    const changes = Array.isArray(entry?.changes) ? entry.changes : [];
    for (const change of changes) {
      const incoming = change?.value?.messages;
      if (!Array.isArray(incoming)) {
        continue;
      }
      for (const message of incoming) {
        if (message?.type !== "text") {
          continue;
        }
        const from = message.from;
        const text = message.text?.body;
        if (typeof from !== "string" || typeof text !== "string" || text.trim() === "") {
          continue;
        }
        messages.push({
          from,
          text: text.trim(),
          messageId: typeof message.id === "string" ? message.id : "",
        });
      }
    }
  }
  return messages;
}

webhookRouter.get("/", (req, res) => {
  const mode = req.query["hub.mode"];
  const token = req.query["hub.verify_token"];
  const challenge = req.query["hub.challenge"];
  if (mode === "subscribe" && token === config.verifyToken && typeof challenge === "string") {
    res.status(200).type("text/plain").send(challenge);
    return;
  }
  res.sendStatus(403);
});

webhookRouter.post("/", async (req, res) => {
  try {
    const signature = verifyMetaSignature(
      req.rawBody,
      req.get("x-hub-signature-256"),
      config.appSecret,
    );
    if (!signature.enforced && !warnedAboutSignature) {
      warnedAboutSignature = true;
      console.warn("X-Hub-Signature-256 no se exige: WHATSAPP_APP_SECRET está vacío.");
    }
    if (!signature.ok) {
      res.sendStatus(403);
      return;
    }

    const messages = extractTextMessages(req.body);
    res.sendStatus(200);

    for (const message of messages) {
      if (alreadyHandled(message.messageId)) {
        continue;
      }
      console.log(`WhatsApp from=${message.from} body=${JSON.stringify(message.text)}`);
      try {
        const reply = handleConversation(message.from, message.text);
        await sendTextMessage(message.from, reply);
      } catch (error) {
        console.error(`No se pudo responder a ${message.from}: ${error.message}`);
      }
    }
  } catch (error) {
    console.error("Webhook inválido:", error.message);
    if (!res.headersSent) {
      res.sendStatus(500);
    }
  }
});
