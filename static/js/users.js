"use strict";

let users = [];

async function load() {
  users = await api("/api/users");
  document.getElementById("rows").innerHTML = users.map((u) => {
    const locked = u.locked_until && new Date(u.locked_until) > new Date();
    return `<tr>
      <td data-label="Name"><strong>${esc(u.full_name)}</strong>${u.id === CURRENT_USER.id ? '<span class="sub">You</span>' : ""}</td>
      <td data-label="Username">${esc(u.username)}</td>
      <td data-label="Role">${badge(u.role, u.role === "admin" ? "Admin" : "HR")}</td>
      <td data-label="Status">${u.is_active ? badge("active", "Active") : badge("inactive", "Inactive")}${locked ? " " + badge("pending", "Locked") : ""}</td>
      <td data-label="Created" class="nowrap">${esc(fmtDate(u.created_at))}</td>
      <td class="actions-cell"><div class="actions"><button class="btn sm" data-edit="${u.id}" type="button">Edit</button></div></td></tr>`;
  }).join("");
}

onReady(async () => {
  await initLayout();
  const dlg = document.getElementById("user-dialog");
  const dialog = bindDialog(dlg, async (v) => {
    const id = v.id;
    if (id) {
      const body = { full_name: v.full_name, role: v.role, is_active: v.is_active };
      if (v.password) body.password = v.password;
      await api(`/api/users/${id}`, { method: "PUT", body });
      toast("User updated");
    } else {
      await api("/api/users", { method: "POST", body: { username: v.username, full_name: v.full_name, role: v.role, password: v.password } });
      toast("User created");
    }
    await load();
  });

  const setMode = (editing) => {
    dialog.form.elements.username.disabled = editing;
    document.getElementById("active-wrap").classList.toggle("hidden", !editing);
    document.getElementById("pwd-label").textContent = editing ? "New password (optional)" : "Password *";
  };

  document.getElementById("add-btn").addEventListener("click", () => {
    setMode(false);
    dialog.open("Add user", { role: "hr", is_active: true });
  });
  document.getElementById("rows").addEventListener("click", (e) => {
    const id = e.target.closest("[data-edit]")?.dataset.edit;
    if (!id) return;
    const u = users.find((x) => String(x.id) === id);
    setMode(true);
    dialog.open(`Edit ${u.full_name}`, { ...u, is_active: Boolean(u.is_active), password: "" });
  });
  await load();
});
