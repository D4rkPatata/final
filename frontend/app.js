"use strict";

const accessView = document.querySelector("#accessView");
const appShell = document.querySelector("#appShell");
const loginForm = document.querySelector("#loginForm");
const dniInput = document.querySelector("#dniInput");
const passwordInput = document.querySelector("#passwordInput");
const passwordToggle = document.querySelector("#passwordToggle");
const loginError = document.querySelector("#loginError");
const guestButton = document.querySelector("#guestButton");
const userArea = document.querySelector("#userArea");
const welcomeTitle = document.querySelector("#welcomeTitle");
const historySuggestion = document.querySelector("#historySuggestion");
const chatForm = document.querySelector("#chatForm");
const messageInput = document.querySelector("#messageInput");
const sendButton = document.querySelector("#sendButton");
const resetButton = document.querySelector("#resetButton");
const chatHistory = document.querySelector("#chatHistory");
const welcomePanel = document.querySelector("#welcomePanel");
const suggestionButtons = document.querySelectorAll("[data-prompt]");
const privacyDialog = document.querySelector("#privacyDialog");
const privacyButton = document.querySelector("#privacyButton");
const closePrivacyButton = document.querySelector("#closePrivacyButton");
const acceptPrivacyButton = document.querySelector("#acceptPrivacyButton");

const SESSION_KEY = "hospitalCheckDemoSession";
const API_BASE_URL = "http://localhost:8000";

// El backend clasifica en administrativa/sintomas/clinica_personal/no_se; el
// frontend usa su propio vocabulario visual (badges, disclaimers). Este mapa
// es la unica traduccion entre ambos.
const CATEGORIA_TO_INTENT = {
  administrativa: "administrativa",
  sintomas: "sintomas",
  clinica_personal: "historial_clinico",
  no_se: "fuera_de_alcance",
};

const INTENT_LABELS = {
  administrativa: "Trámite o información",
  sintomas: "Orientación de salud",
  historial_clinico: "Historial clínico",
  fuera_de_alcance: "Fuera de alcance",
};

let currentSession = null;
let conversation = null;
let isWaitingForResponse = false;
// Sesion activa del arbol de triage multi-turno (null si no hay ninguna en curso).
// Mientras esta activa, las respuestas se dan con los botones del propio mensaje,
// no con el campo de texto libre (se bloquea via setComposerLocked).
let activeTriageSession = null;

function deriveNameParts(nombreCompleto) {
  const partes = nombreCompleto.trim().split(/\s+/);
  const firstName = partes[0] || nombreCompleto;
  const initials =
    partes
      .slice(0, 2)
      .map((parte) => parte[0]?.toUpperCase() ?? "")
      .join("") || "U";
  return { firstName, initials };
}

async function apiFetch(path, body) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    throw new Error(errorBody?.detail || errorBody?.error || `El servidor respondió ${response.status}`);
  }
  return response.json();
}

async function sendQuery(message, session) {
  const body = { texto: message };
  if (session.mode === "authenticated") {
    body.dni = session.dni;
    body.password = session.password;
  }
  return apiFetch("/consulta", body);
}

function mapConsultaResponse(data) {
  const intent = CATEGORIA_TO_INTENT[data.categoria] || "fuera_de_alcance";
  const sources = (data.rag?.fuentes || []).map((fuente) => ({ title: fuente, url: "#fuente-backend" }));
  return {
    intent,
    answer: data.mensaje,
    urgency: "none",
    sources,
    disclaimer: data.rag
      ? "Respuesta generada a partir de los documentos indexados; verifica siempre con el establecimiento de salud."
      : "",
    action: data.requiere_autenticacion ? "login" : undefined,
  };
}

function createElement(tagName, className, text) {
  const element = document.createElement(tagName);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

function saveSession(session) {
  try {
    if (session.mode === "guest") {
      sessionStorage.setItem(SESSION_KEY, JSON.stringify({ mode: "guest" }));
    } else {
      // No se persisten credenciales: una sesion autenticada no sobrevive un
      // refresh de pagina, hay que volver a iniciar sesion.
      sessionStorage.removeItem(SESSION_KEY);
    }
  } catch (error) {
    console.warn("El navegador no permitió guardar la sesión de demostración:", error);
  }
}

function restoreSession() {
  try {
    const stored = JSON.parse(sessionStorage.getItem(SESSION_KEY));
    if (stored?.mode === "guest") return { mode: "guest" };
  } catch (error) {
    console.warn("No se pudo recuperar la sesión de demostración:", error);
  }
  return null;
}

function createAuthenticatedSession(dni, password, nombre) {
  const { firstName, initials } = deriveNameParts(nombre);
  return { mode: "authenticated", dni, password, name: nombre, firstName, initials };
}

function renderUserArea() {
  userArea.replaceChildren();

  if (currentSession.mode === "guest") {
    const loginButton = createElement("button", "header-login-button", "Iniciar sesión");
    loginButton.type = "button";
    loginButton.addEventListener("click", endSession);
    userArea.append(loginButton);
    return;
  }

  const profile = createElement("div", "user-profile");
  const avatar = createElement("span", "user-profile__avatar", currentSession.initials);
  avatar.setAttribute("aria-hidden", "true");
  const info = createElement("span", "user-profile__info");
  const name = createElement("strong", "", currentSession.name);
  const logoutButton = createElement("button", "logout-button", "Cerrar sesión");
  logoutButton.type = "button";
  logoutButton.addEventListener("click", endSession);
  info.append(name, logoutButton);
  profile.append(avatar, info);
  userArea.append(profile);
}

function enterApplication(session) {
  currentSession = session;
  saveSession(session);
  accessView.hidden = true;
  appShell.hidden = false;
  historySuggestion.hidden = session.mode !== "authenticated";
  welcomeTitle.textContent =
    session.mode === "authenticated"
      ? `Hola, ${session.firstName}, ¿cómo podemos orientarte?`
      : "Hola, ¿cómo podemos orientarte?";
  renderUserArea();
  messageInput.focus();
}

function endSession() {
  try {
    sessionStorage.removeItem(SESSION_KEY);
  } catch (error) {
    console.warn("No se pudo limpiar la sesión de demostración:", error);
  }
  clearConversation(false);
  currentSession = null;
  appShell.hidden = true;
  accessView.hidden = false;
  loginForm.reset();
  passwordInput.type = "password";
  passwordToggle.querySelector(".sr-only").textContent = "Mostrar contraseña";
  hideLoginError();
  dniInput.focus();
}

function showLoginError(message) {
  loginError.textContent = message;
  loginError.hidden = false;
  dniInput.setAttribute("aria-invalid", "true");
  passwordInput.setAttribute("aria-invalid", "true");
}

function hideLoginError() {
  loginError.hidden = true;
  loginError.textContent = "";
  dniInput.removeAttribute("aria-invalid");
  passwordInput.removeAttribute("aria-invalid");
}

async function handleLogin(event) {
  event.preventDefault();
  const dni = dniInput.value.trim();
  const password = passwordInput.value;
  hideLoginError();

  try {
    const response = await fetch(`${API_BASE_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dni, password }),
    });
    const data = await response.json();

    if (!response.ok || !data.autenticado) {
      showLoginError(data.mensaje || "DNI o contraseña incorrectos.");
      passwordInput.select();
      return;
    }

    enterApplication(createAuthenticatedSession(dni, password, data.nombre));
  } catch (error) {
    console.error("Error al iniciar sesión:", error);
    showLoginError("No se pudo conectar con el servidor. Verifica que el backend esté corriendo.");
  }
}

function ensureConversation() {
  if (conversation) return;
  welcomePanel.hidden = true;
  conversation = createElement("div", "conversation");
  chatHistory.append(conversation);
}

function createAssistantAvatar() {
  const avatar = createElement("span", "assistant-avatar");
  avatar.setAttribute("aria-hidden", "true");
  avatar.innerHTML = `
    <svg viewBox="0 0 24 24">
      <path d="M8.8 4.5h6.4v4.3h4.3v6.4h-4.3v4.3H8.8v-4.3H4.5V8.8h4.3V4.5Z"></path>
    </svg>`;
  return avatar;
}

function createMessageShell(role) {
  const article = createElement("article", `message message--${role}`);
  const body = createElement("div", "message__body");
  const label = createElement(
    "span",
    "message__label",
    role === "user" ? "Tú" : "Asistente virtual",
  );
  const bubble = createElement("div", "message__bubble");
  body.append(label, bubble);
  if (role === "assistant") article.append(createAssistantAvatar());
  article.append(body);
  return { article, bubble };
}

function appendUserMessage(message) {
  ensureConversation();
  const { article, bubble } = createMessageShell("user");
  bubble.textContent = message;
  conversation.append(article);
  scrollToLatestMessage();
}

function appendParagraphs(container, text) {
  text.split(/\n\s*\n/).forEach((paragraphText) => {
    container.append(createElement("p", "", paragraphText));
  });
}

function appendEmergencyAlert(container) {
  const alert = createElement("div", "emergency-alert");
  alert.setAttribute("role", "alert");
  alert.innerHTML = `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 3.5 21 20H3L12 3.5Z"></path>
      <path d="M12 9v5M12 17v.1"></path>
    </svg>
    <div>
      <strong>Busca atención inmediata</strong>
      <span>Lo que describes podría ser una señal de alarma. Acude al establecimiento de salud más cercano o contacta a emergencias.</span>
    </div>`;
  container.append(alert);
}

function appendHumanReviewAlert(container) {
  const alert = createElement("div", "human-review-alert");
  alert.setAttribute("role", "status");
  alert.innerHTML = `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="9"></circle>
      <path d="M12 8v5M12 15.5v.1"></path>
    </svg>
    <div>
      <strong>Revisión humana recomendada</strong>
      <span>No hay información suficiente para orientar con seguridad. Te recomendamos que un profesional de salud evalúe tu caso.</span>
    </div>`;
  container.append(alert);
}

function appendIntentBadge(container, intent) {
  const modifiers = {
    sintomas: "symptoms",
    historial_clinico: "history",
    fuera_de_alcance: "outside",
    administrativa: "admin",
  };
  const badge = createElement(
    "span",
    `intent-badge intent-badge--${modifiers[intent]}`,
    INTENT_LABELS[intent],
  );
  container.append(badge);
}

function appendSources(container, sources) {
  if (!sources?.length) return;
  const section = createElement("div", "sources");
  const title = createElement("div", "sources__title");
  title.append(document.createTextNode("Fuente"));
  section.append(title);

  sources.forEach((source) => {
    const link = createElement("a", "", source.title);
    link.href = source.url || "#fuente-backend";
    link.setAttribute("aria-label", `${source.title}. Enlace no disponible en el prototipo.`);
    link.addEventListener("click", (event) => event.preventDefault());
    section.append(link);
  });
  container.append(section);
}

function appendResponseAction(container, action) {
  if (action !== "login") return;
  const button = createElement("button", "inline-login-button", "Iniciar sesión");
  button.type = "button";
  button.addEventListener("click", endSession);
  container.append(button);
}

function appendAssistantResponse(response) {
  const { article, bubble } = createMessageShell("assistant");
  appendIntentBadge(bubble, response.intent);
  if (response.urgency === "emergency") appendEmergencyAlert(bubble);
  else if (response.urgency === "humano") appendHumanReviewAlert(bubble);
  appendParagraphs(bubble, response.answer);
  appendSources(bubble, response.sources);
  appendResponseAction(bubble, response.action);
  if (response.disclaimer) bubble.append(createElement("p", "disclaimer", response.disclaimer));
  conversation.append(article);
  scrollToLatestMessage();
}

function appendTypingIndicator() {
  const { article, bubble } = createMessageShell("assistant");
  article.id = "typingIndicator";
  article.setAttribute("aria-label", "El asistente está analizando la consulta");
  bubble.classList.add("typing");
  bubble.innerHTML = "<span></span><span></span><span></span>";
  conversation.append(article);
  scrollToLatestMessage();
  return article;
}

function appendErrorMessage() {
  const { article, bubble } = createMessageShell("assistant");
  appendParagraphs(
    bubble,
    "No pude procesar tu consulta en este momento. Intenta nuevamente en unos instantes.",
  );
  conversation.append(article);
  scrollToLatestMessage();
}

function scrollToLatestMessage() {
  window.requestAnimationFrame(() => {
    chatHistory.scrollTop = chatHistory.scrollHeight;
  });
}

// --- Arbol de triage multi-turno: widget de "respuesta rápida" ------------

function disableQuickReplies(container) {
  container.querySelectorAll("button, input, select").forEach((el) => (el.disabled = true));
}

function buildContextoForm(paso) {
  const container = createElement("div", "quick-replies quick-replies--form");
  const form = createElement("form", "triage-context-form");
  const campos = {};

  paso.preguntas_contexto.forEach((pregunta) => {
    const wrapper = createElement("label", "triage-context-field");
    wrapper.append(createElement("span", "", pregunta.texto));

    let input;
    if (pregunta.tipo === "numero") {
      input = document.createElement("input");
      input.type = "number";
      if (pregunta.min != null) input.min = String(pregunta.min);
      if (pregunta.max != null) input.max = String(pregunta.max);
    } else if (pregunta.tipo === "opcion") {
      input = document.createElement("select");
      pregunta.opciones.forEach((valor) => {
        const opt = document.createElement("option");
        opt.value = valor;
        opt.textContent = valor.replace(/_/g, " ");
        input.append(opt);
      });
    } else if (pregunta.tipo === "booleano") {
      input = document.createElement("select");
      [["false", "No"], ["true", "Sí"]].forEach(([valor, texto]) => {
        const opt = document.createElement("option");
        opt.value = valor;
        opt.textContent = texto;
        input.append(opt);
      });
    } else {
      input = document.createElement("input");
      input.type = "text";
    }
    if (pregunta.requerido) input.required = true;

    wrapper.append(input);
    form.append(wrapper);
    campos[pregunta.id] = input;
  });

  const submitBtn = createElement("button", "quick-reply-submit", "Continuar");
  submitBtn.type = "submit";
  form.append(submitBtn);

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    disableQuickReplies(form);
    runTriageStep(() =>
      apiFetch("/triaje/contexto", {
        session_id: paso.session_id,
        edad: Number(campos.edad.value),
        embarazo: campos.embarazo.value,
        duracion: campos.duracion.value,
        empeoramiento: campos.empeoramiento.value === "true",
      }),
    );
  });

  container.append(form);
  return container;
}

function buildOpcionesWidget(paso) {
  const container = createElement("div", "quick-replies");
  const seleccionadas = new Set();

  paso.opciones.forEach((opcion) => {
    const btn = createElement("button", "quick-reply-option", opcion.texto);
    btn.type = "button";

    if (paso.seleccion_multiple) {
      btn.addEventListener("click", () => {
        btn.classList.toggle("is-selected");
        if (seleccionadas.has(opcion.id)) seleccionadas.delete(opcion.id);
        else seleccionadas.add(opcion.id);
      });
    } else {
      btn.addEventListener("click", () => {
        disableQuickReplies(container);
        const endpoint = paso.etapa === "seleccion_motivo" ? "/triaje/motivo" : "/triaje/responder";
        const body =
          paso.etapa === "seleccion_motivo"
            ? { session_id: paso.session_id, motivo: opcion.id }
            : { session_id: paso.session_id, respuesta: opcion.id };
        runTriageStep(() => apiFetch(endpoint, body));
      });
    }
    container.append(btn);
  });

  if (paso.seleccion_multiple) {
    const continuar = createElement("button", "quick-reply-submit", "Continuar");
    continuar.type = "button";
    continuar.addEventListener("click", () => {
      disableQuickReplies(container);
      runTriageStep(() =>
        apiFetch("/triaje/filtro-emergencia", {
          session_id: paso.session_id,
          opciones: Array.from(seleccionadas),
        }),
      );
    });
    container.append(continuar);
  }

  return container;
}

function appendTriageBubble(paso) {
  ensureConversation();
  const { article, bubble } = createMessageShell("assistant");
  appendIntentBadge(bubble, "sintomas");

  const texto = paso.advertencia ? `${paso.advertencia}\n\n${paso.pregunta ?? ""}` : paso.pregunta;
  if (texto) appendParagraphs(bubble, texto);

  const widget = paso.etapa === "contexto" ? buildContextoForm(paso) : buildOpcionesWidget(paso);
  bubble.append(widget);

  conversation.append(article);
  scrollToLatestMessage();
}

function appendTriageResultado(resultado) {
  const urgencia =
    resultado.nivel === "rojo" || resultado.nivel === "naranja"
      ? "emergency"
      : resultado.nivel === "humano"
        ? "humano"
        : "none";
  appendAssistantResponse({
    intent: "sintomas",
    answer: resultado.mensaje,
    urgency: urgencia,
    sources: [],
    disclaimer: resultado.disclaimer,
  });
}

function setComposerLocked(locked) {
  messageInput.disabled = locked;
  messageInput.placeholder = locked ? "Responde usando las opciones de arriba…" : "Escribe aquí tu consulta…";
  updateComposerState();
}

async function runTriageStep(fetchPasoTriage) {
  try {
    const paso = await fetchPasoTriage();
    if (paso.finalizado) {
      activeTriageSession = null;
      appendTriageResultado(paso.resultado);
      setComposerLocked(false);
    } else {
      activeTriageSession = { sessionId: paso.session_id, etapa: paso.etapa };
      appendTriageBubble(paso);
    }
  } catch (error) {
    console.error("Error en el árbol de triage:", error);
    activeTriageSession = null;
    appendErrorMessage();
    setComposerLocked(false);
  } finally {
    scrollToLatestMessage();
  }
}

// ---------------------------------------------------------------------------

function resizeTextarea() {
  messageInput.style.height = "auto";
  messageInput.style.height = `${Math.min(messageInput.scrollHeight, 120)}px`;
}

function updateComposerState() {
  sendButton.disabled = isWaitingForResponse || messageInput.disabled || messageInput.value.trim().length === 0;
}

function setWaitingState(waiting) {
  isWaitingForResponse = waiting;
  updateComposerState();
}

async function handleSubmit(event) {
  event.preventDefault();
  const message = messageInput.value.trim();
  if (!message || isWaitingForResponse || messageInput.disabled) return;

  appendUserMessage(message);
  messageInput.value = "";
  resizeTextarea();
  setWaitingState(true);
  const typingIndicator = appendTypingIndicator();

  try {
    const data = await sendQuery(message, currentSession);
    typingIndicator.remove();

    if (data.triage_paso && !data.triage_paso.finalizado) {
      activeTriageSession = { sessionId: data.triage_paso.session_id, etapa: data.triage_paso.etapa };
      appendTriageBubble(data.triage_paso);
    } else {
      appendAssistantResponse(mapConsultaResponse(data));
    }
  } catch (error) {
    console.error("Error al procesar la consulta:", error);
    typingIndicator.remove();
    appendErrorMessage();
  } finally {
    setWaitingState(false);
    setComposerLocked(!!activeTriageSession);
    messageInput.focus();
  }
}

function clearConversation(shouldFocus = true) {
  conversation?.remove();
  conversation = null;
  activeTriageSession = null;
  welcomePanel.hidden = false;
  messageInput.value = "";
  setComposerLocked(false);
  resizeTextarea();
  setWaitingState(false);
  chatHistory.scrollTop = 0;
  if (shouldFocus) messageInput.focus();
}

suggestionButtons.forEach((button) => {
  button.addEventListener("click", () => {
    messageInput.value = button.dataset.prompt;
    resizeTextarea();
    updateComposerState();
    messageInput.focus();
    messageInput.setSelectionRange(messageInput.value.length, messageInput.value.length);
  });
});

loginForm.addEventListener("submit", handleLogin);
guestButton.addEventListener("click", () => enterApplication({ mode: "guest" }));
dniInput.addEventListener("input", () => {
  dniInput.value = dniInput.value.replace(/\D/g, "").slice(0, 8);
  hideLoginError();
});
passwordInput.addEventListener("input", hideLoginError);
passwordToggle.addEventListener("click", () => {
  const showPassword = passwordInput.type === "password";
  passwordInput.type = showPassword ? "text" : "password";
  passwordToggle.querySelector(".sr-only").textContent =
    showPassword ? "Ocultar contraseña" : "Mostrar contraseña";
  passwordInput.focus();
});

messageInput.addEventListener("input", () => {
  resizeTextarea();
  updateComposerState();
});
messageInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    chatForm.requestSubmit();
  }
});

chatForm.addEventListener("submit", handleSubmit);
resetButton.addEventListener("click", () => clearConversation());
privacyButton.addEventListener("click", () => privacyDialog.showModal());
closePrivacyButton.addEventListener("click", () => privacyDialog.close());
acceptPrivacyButton.addEventListener("click", () => privacyDialog.close());
privacyDialog.addEventListener("click", (event) => {
  if (event.target === privacyDialog) privacyDialog.close();
});

const restoredSession = restoreSession();
if (restoredSession) enterApplication(restoredSession);
else dniInput.focus();
updateComposerState();
