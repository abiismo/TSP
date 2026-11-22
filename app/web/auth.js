"use strict";

(() => {
  const modal = document.querySelector("#login-dialog");
  const form = document.querySelector("#login-form");
  const open = document.querySelector("#open-login");
  const submit = document.querySelector("#submit-login");
  const password = document.querySelector("#login-password");
  const reveal = document.querySelector("#toggle-password");
  const error = document.querySelector("#login-error");
  const notice = document.querySelector("#account-notice");
  const logout = document.querySelector("#logout");
  let csrfToken = "";
  let submitting = false;

  function announce(text) {
    notice.textContent = text;
    notice.hidden = !text;
  }

  function renderSession(session) {
    const authenticated = session.authenticated === true;
    csrfToken = authenticated ? session.csrf_token : "";
    open.hidden = authenticated;
    document.querySelector("#account-panel").hidden = !authenticated;
    document.querySelector("#account-name").textContent = authenticated ? `Hola, ${session.user.name}` : "";
  }

  async function api(path, data, signal) {
    const options = { credentials: "same-origin", cache: "no-store", signal };
    if (data !== undefined) {
      options.method = "POST";
      options.headers = { "Content-Type": "application/json" };
      if (csrfToken) options.headers["X-CSRF-Token"] = csrfToken;
      options.body = JSON.stringify(data);
    }
    const response = await fetch(path, options);
    const result = await response.json();
    if (!response.ok) {
      const failure = new Error(result.error || "No pudimos completar la solicitud.");
      failure.status = response.status;
      throw failure;
    }
    return result;
  }

  async function refreshSession() {
    try {
      renderSession(await api("/api/auth/session"));
    } catch {
      announce("No pudimos comprobar tu sesión. Puedes volver a intentarlo al entrar.");
    } finally {
      open.disabled = false;
    }
  }

  open.addEventListener("click", () => {
    error.hidden = true;
    modal.showModal();
    document.querySelector("#login-email").focus();
  });
  document.querySelector("#close-login").addEventListener("click", () => modal.close());
  modal.addEventListener("close", () => {
    password.value = "";
    password.type = "password";
    reveal.textContent = "Mostrar";
    reveal.setAttribute("aria-label", "Mostrar contraseña");
    reveal.setAttribute("aria-pressed", "false");
  });
  reveal.addEventListener("click", () => {
    const show = password.type === "password";
    password.type = show ? "text" : "password";
    reveal.textContent = show ? "Ocultar" : "Mostrar";
    reveal.setAttribute("aria-label", show ? "Ocultar contraseña" : "Mostrar contraseña");
    reveal.setAttribute("aria-pressed", String(show));
  });

  form.addEventListener("submit", async event => {
    event.preventDefault();
    if (submitting || !form.reportValidity()) return;
    submitting = true;
    submit.disabled = true;
    form.setAttribute("aria-busy", "true");
    submit.textContent = "Entrando…";
    error.hidden = true;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const session = await api("/api/auth/login", {
        email: form.elements.email.value.trim(), password: password.value,
      }, controller.signal);
      renderSession(session);
      modal.close();
      form.reset();
      announce("Ya iniciaste sesión. Puedes seguir explorando el catálogo.");
      logout.focus();
    } catch (failure) {
      error.textContent = failure.status ? failure.message : "No pudimos conectar. Revisa tu conexión y vuelve a intentarlo.";
      error.hidden = false;
      password.value = "";
      if (modal.open) password.focus();
    } finally {
      clearTimeout(timeout);
      submitting = false;
      submit.disabled = false;
      form.setAttribute("aria-busy", "false");
      submit.textContent = "Entrar a mi cuenta";
    }
  });

  logout.addEventListener("click", async () => {
    logout.disabled = true;
    try {
      renderSession(await api("/api/auth/logout", {}));
      announce("Cerraste tu sesión.");
      open.focus();
    } catch (failure) {
      if (failure.status === 401) {
        renderSession({ authenticated: false });
        open.focus();
      }
      announce(failure.status ? failure.message : "No pudimos cerrar tu sesión. Revisa tu conexión y vuelve a intentarlo.");
    } finally {
      logout.disabled = false;
    }
  });

  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible" && !submitting) refreshSession();
  });
  refreshSession();
})();
