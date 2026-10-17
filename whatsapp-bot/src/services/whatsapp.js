import axios from "axios";

import { config } from "../config.js";

/**
 * Envía un mensaje de texto por la Cloud API.
 * No registra el token. Si Meta rechaza la petición, deja el cuerpo de error en consola.
 *
 * @param {string} to Número de destino, solo dígitos.
 * @param {string} body Texto saliente.
 */
export async function sendTextMessage(to, body) {
  const url = `https://graph.facebook.com/${config.graphVersion}/${config.phoneNumberId}/messages`;
  try {
    const response = await axios.post(
      url,
      {
        messaging_product: "whatsapp",
        recipient_type: "individual",
        to,
        type: "text",
        text: { preview_url: false, body },
      },
      {
        headers: {
          Authorization: `Bearer ${config.token}`,
          "Content-Type": "application/json",
        },
        timeout: 15000,
      },
    );
    return response.data;
  } catch (error) {
    const detail = error.response?.data ?? { message: error.message };
    console.error("WhatsApp Cloud API error:", JSON.stringify(detail));
    throw error;
  }
}
