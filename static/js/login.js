"use strict";

document.getElementById("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  const values = formValues(form);
  if (!values.username.trim() || !values.password) {
    showFormError(form, "Enter your username and password.");
    return;
  }
  const btn = form.querySelector("button");
  btn.disabled = true;
  showFormError(form, "");
  try {
    await api("/api/auth/login", { method: "POST", body: values });
    window.location.href = "/";
  } catch (err) {
    showFormError(form, err.message);
    form.password.value = "";
    form.password.focus();
  } finally {
    btn.disabled = false;
  }
});
