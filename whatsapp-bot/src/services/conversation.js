/**
 * Respuesta temporal del reporte de agua. Sustituye el cuerpo de esta función
 * por OpenAI o por la base propia sin cambiar la firma:
 * handleConversation(from, messageText).
 *
 * @param {string} from Número de WhatsApp que escribió, sin el signo +.
 * @param {string} messageText Texto recibido.
 * @returns {string} Texto que se enviará de vuelta.
 */
export function handleConversation(from, messageText) {
  if (typeof from !== "string" || from.trim() === "") {
    throw new Error("from es obligatorio");
  }
  const normalized = messageText.trim().toLocaleLowerCase("es");
  const greeting = /^(hola|buenas|buenos dias|buen dia|hey|hi)\b/.test(normalized);

  if (greeting || normalized.length < 12) {
    return "Hola. Escribe el lugar, hace cuánto no hay agua y cuántas personas son.";
  }

  return "Listo. Ya recibimos tu mensaje. Una persona lo revisa.";
}
