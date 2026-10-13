"use strict";

onReady(async () => {
  const user = await initLayout();
  document.getElementById("who").textContent = `${user.full_name} · ${user.username} · ${user.role === "admin" ? "Administrator" : "HR"}`;
  const form = document.getElementById("pwd-form");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const v = formValues(form);
    if (v.new_password !== v.confirm) return showFormError(form, "New passwords do not match.");
    showFormError(form, "");
    try {
      await api("/api/auth/change-password", { method: "POST", body: { current_password: v.current_password, new_password: v.new_password } });
      form.reset();
      toast("Password updated");
    } catch (err) { showFormError(form, err.message); }
  });
});
