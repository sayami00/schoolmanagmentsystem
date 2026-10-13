"use strict";

const el = (id) => document.getElementById(id);
let leaves = [];

const cap = (s) => s[0].toUpperCase() + s.slice(1);

async function loadEmployees() {
  const data = await api("/api/employees?status=active&page_size=500");
  const opts = data.items.map((e) => `<option value="${e.id}">${esc(e.first_name)} ${esc(e.last_name)} (${esc(e.emp_code)})</option>`).join("");
  el("f-emp").innerHTML = '<option value="">All employees</option>' + opts;
  document.querySelector('#leave-dialog select[name="employee_id"]').innerHTML = '<option value="">Select employee</option>' + opts;
}

async function load() {
  leaves = await api(`/api/leaves${qs({ status: el("f-status").value, month: el("f-month").value, employee_id: el("f-emp").value })}`);
  const isAdmin = CURRENT_USER.role === "admin";
  el("count").textContent = `${leaves.length} record${leaves.length === 1 ? "" : "s"}`;
  el("rows").innerHTML = leaves.map((l) => {
    const actions = [];
    if (l.status === "pending") {
      actions.push(`<button class="btn sm" data-act="approved" data-id="${l.id}" type="button">Approve</button>`,
        `<button class="btn sm" data-act="rejected" data-id="${l.id}" type="button">Reject</button>`,
        `<button class="btn sm" data-act="edit" data-id="${l.id}" type="button">Edit</button>`);
    }
    if (l.status !== "approved" || isAdmin) {
      actions.push(`<button class="btn sm danger" data-act="delete" data-id="${l.id}" type="button">Delete</button>`);
    }
    const reviewed = l.reviewed_by_name ? `<span class="sub">by ${esc(l.reviewed_by_name)}</span>` : "";
    return `<tr>
      <td data-label="Employee"><strong>${esc(l.employee_name)}</strong><span class="sub">${esc(l.emp_code)} · ${esc(l.department_name)}</span></td>
      <td data-label="Type">${esc(LEAVE_TYPES[l.leave_type])}</td>
      <td data-label="Dates" class="nowrap">${esc(fmtDate(l.start_date))}${l.end_date !== l.start_date ? ` – ${esc(fmtDate(l.end_date))}` : ""}</td>
      <td data-label="Days" class="num">${l.days}</td>
      <td data-label="Reason">${esc(l.reason) || '<span class="muted">—</span>'}</td>
      <td data-label="Status">${badge(l.status, cap(l.status))}${reviewed}</td>
      <td class="actions-cell"><div class="actions">${actions.join("")}</div></td></tr>`;
  }).join("") || '<tr><td colspan="7" class="empty">No leave records match these filters.</td></tr>';
}

onReady(async () => {
  await initLayout();
  await loadEmployees();

  const dialog = bindDialog(el("leave-dialog"), async (v) => {
    const id = v.id;
    delete v.id;
    if (v.start_date && v.end_date && v.end_date < v.start_date) throw new Error("End date cannot be before start date");
    if (id) await api(`/api/leaves/${id}`, { method: "PUT", body: v });
    else await api("/api/leaves", { method: "POST", body: v });
    toast(id ? "Leave updated" : "Leave recorded as pending");
    await load();
  });
  const startInput = dialog.form.elements.start_date;
  startInput.addEventListener("change", () => {
    const end = dialog.form.elements.end_date;
    end.min = startInput.value;
    if (!end.value || end.value < startInput.value) end.value = startInput.value;
  });

  el("add-btn").addEventListener("click", () => dialog.open("Record leave", { leave_type: "annual" }));
  ["f-status", "f-month", "f-emp"].forEach((id) => el(id).addEventListener("change", () => load().catch((e) => toast(e.message, "error"))));

  el("rows").addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-act]");
    if (!btn) return;
    const leave = leaves.find((l) => String(l.id) === btn.dataset.id);
    const act = btn.dataset.act;
    try {
      if (act === "edit") {
        dialog.open(`Edit leave · ${leave.employee_name}`, leave);
        dialog.form.elements.end_date.min = leave.start_date;
        return;
      }
      if (act === "delete") {
        if (!(await confirmDialog(`Delete this ${leave.status} leave record for ${leave.employee_name}?`))) return;
        await api(`/api/leaves/${leave.id}`, { method: "DELETE" });
        toast("Leave deleted");
      } else {
        const verb = act === "approved" ? "Approve" : "Reject";
        if (!(await confirmDialog(`${verb} ${leave.days}-day ${LEAVE_TYPES[leave.leave_type].toLowerCase()} leave for ${leave.employee_name}?`,
          { okLabel: verb, danger: act === "rejected" }))) return;
        await api(`/api/leaves/${leave.id}/status`, { method: "POST", body: { status: act } });
        toast(`Leave ${act}`);
      }
      await load();
    } catch (err) { toast(err.message, "error"); }
  });

  await load();
});
