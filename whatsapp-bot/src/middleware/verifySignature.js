import crypto from "node:crypto";

/**
 * Comprueba X-Hub-Signature-256 de Meta.
 * Si appSecret está vacío, no exige la firma: el punto de enganche queda listo
 * para activarse en cuanto se configure WHATSAPP_APP_SECRET.
 */
export function verifyMetaSignature(rawBody, signatureHeader, appSecret) {
  if (!appSecret) {
    return { ok: true, enforced: false };
  }
  if (!Buffer.isBuffer(rawBody) || typeof signatureHeader !== "string") {
    return { ok: false, enforced: true };
  }
  const prefix = "sha256=";
  if (!signatureHeader.startsWith(prefix)) {
    return { ok: false, enforced: true };
  }
  const expected = crypto.createHmac("sha256", appSecret).update(rawBody).digest("hex");
  const received = signatureHeader.slice(prefix.length);
  const expectedBuffer = Buffer.from(expected, "utf8");
  const receivedBuffer = Buffer.from(received, "utf8");
  if (expectedBuffer.length !== receivedBuffer.length) {
    return { ok: false, enforced: true };
  }
  return {
    ok: crypto.timingSafeEqual(expectedBuffer, receivedBuffer),
    enforced: true,
  };
}
