"use strict";

let departments = [];

async function load() {
  departments = await api("/api/departments");
  const isAdmin = CURRENT_USER.role === "admin";
  document.getElementById("count").textContent = `${departments.length} department${departments.length === 1 ? "" : "s"}`;
  document.getElementById("rows").innerHTML = departments.map((d) => `<tr>
      <td data-label="Name"><strong>${esc(d.name)}</strong></td>
      <td data-label="Code">${esc(d.code)}</td>
      <td data-label="Description">${esc(d.description) || '<span class="muted">—</span>'}</td>
      <td data-label="Active staff" class="num">${d.active_count}</td>
      <td data-label="Total staff" class="num">${d.employee_count}</td>
      <td class="actions-cell"><div class="actions">
        <button class="btn sm" data-edit="${d.id}" type="button">Edit</button>
        ${isAdmin ? `<button class="btn sm danger" data-del="${d.id}" type="button">Delete</button>` : ""}
      </div></td></tr>`).join("")
    || '<tr><td colspan="6" class="empty">No departments yet. Add your first one.</td></tr>';
}

onReady(async () => {
  await initLayout();
  const dialog = bindDialog(document.getElementById("dept-dialog"), async (v) => {
    const id = v.id;
    delete v.id;
    if (id) await api(`/api/departments/${id}`, { method: "PUT", body: v });
    else await api("/api/departments", { method: "POST", body: v });
    toast(id ? "Department updated" : "Department added");
    await load();
  });

  document.getElementById("add-btn").addEventListener("click", () => dialog.open("Add department"));
  document.getElementById("rows").addEventListener("click", async (e) => {
    const editId = e.target.closest("[data-edit]")?.dataset.edit;
    const delId = e.target.closest("[data-del]")?.dataset.del;
    const dept = departments.find((d) => String(d.id) === (editId || delId));
    if (editId) dialog.open(`Edit ${dept.name}`, dept);
    if (delId) {
      if (!(await confirmDialog(`Delete the ${dept.name} department?`))) return;
      try {
        await api(`/api/departments/${delId}`, { method: "DELETE" });
        toast("Department deleted");
        await load();
      } catch (err) { toast(err.message, "error"); }
    }
  });
  await load();
});
