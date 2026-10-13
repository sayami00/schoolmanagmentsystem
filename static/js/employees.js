"use strict";

const PAGE_SIZE = 15;
const state = { page: 1, total: 0, items: [] };
const el = (id) => document.getElementById(id);

async function load() {
  const data = await api(`/api/employees${qs({
    q: el("q").value.trim(), department_id: el("f-dept").value, status: el("f-status").value,
    page: state.page, page_size: PAGE_SIZE,
  })}`);
  Object.assign(state, { total: data.total, items: data.items });
  render();
}

function render() {
  const isAdmin = CURRENT_USER.role === "admin";
  el("rows").innerHTML = state.items.map((e) => `<tr>
      <td data-label="Employee"><strong>${esc(e.first_name)} ${esc(e.last_name)}</strong><span class="sub">${esc(e.email)}</span></td>
      <td data-label="Code" class="nowrap">${esc(e.emp_code)}</td>
      <td data-label="Department">${esc(e.department_name)}</td>
      <td data-label="Designation">${esc(e.designation) || '<span class="muted">—</span>'}</td>
      <td data-label="Hire date" class="nowrap">${esc(fmtDate(e.hire_date))}</td>
      <td data-label="Status">${badge(e.status, e.status === "active" ? "Active" : "Inactive")}</td>
      <td class="actions-cell"><div class="actions">
        <button class="btn sm" data-edit="${e.id}" type="button">Edit</button>
        ${isAdmin ? `<button class="btn sm danger" data-del="${e.id}" type="button">Delete</button>` : ""}
      </div></td></tr>`).join("")
    || '<tr><td colspan="7" class="empty">No employees match these filters.</td></tr>';

  const pages = Math.max(1, Math.ceil(state.total / PAGE_SIZE));
  const from = state.total ? (state.page - 1) * PAGE_SIZE + 1 : 0;
  el("page-info").textContent = `${from}–${Math.min(state.page * PAGE_SIZE, state.total)} of ${state.total}`;
  el("count").textContent = `${state.total} employee${state.total === 1 ? "" : "s"} shown`;
  el("prev").disabled = state.page <= 1;
  el("next").disabled = state.page >= pages;
}

onReady(async () => {
  await initLayout();
  await Promise.all([
    loadDepartmentOptions(el("f-dept"), { includeAll: true }),
    loadDepartmentOptions(document.querySelector('#emp-dialog select[name="department_id"]')),
  ]);

  const dialog = bindDialog(el("emp-dialog"), async (v) => {
    const id = v.id;
    delete v.id;
    if (id) await api(`/api/employees/${id}`, { method: "PUT", body: v });
    else await api("/api/employees", { method: "POST", body: v });
    toast(id ? "Employee updated" : "Employee added");
    await load();
  });

  const refilter = () => { state.page = 1; load().catch((e) => toast(e.message, "error")); };
  el("q").addEventListener("input", debounce(refilter));
  el("f-dept").addEventListener("change", refilter);
  el("f-status").addEventListener("change", refilter);
  el("prev").addEventListener("click", () => { state.page -= 1; load(); });
  el("next").addEventListener("click", () => { state.page += 1; load(); });
  el("add-btn").addEventListener("click", () => dialog.open("Add employee", { status: "active", hire_date: todayISO() }));

  el("rows").addEventListener("click", async (e) => {
    const editId = e.target.closest("[data-edit]")?.dataset.edit;
    const delId = e.target.closest("[data-del]")?.dataset.del;
    if (editId) {
      const emp = state.items.find((x) => String(x.id) === editId);
      dialog.open(`Edit ${emp.first_name} ${emp.last_name}`, emp);
    } else if (delId) {
      const emp = state.items.find((x) => String(x.id) === delId);
      const ok = await confirmDialog(`Delete ${emp.first_name} ${emp.last_name}? All of their attendance and leave records will also be deleted. To keep history, set the status to Inactive instead.`);
      if (!ok) return;
      try {
        await api(`/api/employees/${delId}`, { method: "DELETE" });
        toast("Employee deleted");
        await load();
      } catch (err) { toast(err.message, "error"); }
    }
  });

  await load();
});
