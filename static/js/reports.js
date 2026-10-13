"use strict";

const el = (id) => document.getElementById(id);

function cells(r) {
  return `<td data-label="Present" class="num">${r.present}</td>
    <td data-label="Late" class="num">${r.late}</td>
    <td data-label="Half day" class="num">${r.half_day}</td>
    <td data-label="Absent" class="num">${r.absent}</td>
    <td data-label="On leave" class="num">${r.on_leave}</td>
    <td data-label="Days marked" class="num">${r.days_marked}</td>
    <td data-label="Approved leave days" class="num">${r.approved_leave_days}</td>
    <td data-label="Rate" class="num">${esc(fmtRate(r.attendance_rate))}</td>`;
}

async function load() {
  const params = { month: el("month").value, department_id: el("f-dept").value };
  const r = await api(`/api/reports/monthly${qs(params)}`);
  el("csv").href = `/api/reports/monthly.csv${qs(params)}`;
  const deptName = el("f-dept").selectedOptions[0]?.textContent || "All departments";
  const [y, m] = r.month.split("-").map(Number);
  el("title").textContent = `${new Date(y, m - 1, 1).toLocaleDateString(undefined, { month: "long", year: "numeric" })} · ${deptName}`;

  const t = r.totals;
  el("stats").innerHTML = [
    ["Attendance rate", fmtRate(t.attendance_rate), ""], ["Present", t.present, "good"], ["Late", t.late, "warn"],
    ["Half day", t.half_day, "info"], ["Absent", t.absent, "bad"], ["On leave", t.on_leave, "leave"],
  ].map(([label, v, dot]) => `<div class="stat${dot ? "" : " hero"}"><div class="label">${dot ? `<span class="dot ${dot}"></span>` : ""}${esc(label)}</div>
      <div class="value">${esc(v)}</div></div>`).join("");

  el("rows").innerHTML = r.items.map((it) => `<tr>
      <td data-label="Employee"><strong>${esc(it.name)}</strong><span class="sub">${esc(it.emp_code)}${
        it.employee_status === "inactive" ? " · inactive" : ""}</span></td>
      <td data-label="Department">${esc(it.department_name)}</td>${cells(it)}</tr>`).join("")
    || '<tr><td colspan="10" class="empty">No employees in this period.</td></tr>';
  el("foot").innerHTML = r.items.length ? `<tr><td data-label="">Total</td><td data-label=""></td>${cells(t)}</tr>` : "";
}

onReady(async () => {
  await initLayout();
  await loadDepartmentOptions(el("f-dept"), { includeAll: true });
  el("month").value = todayISO().slice(0, 7);
  el("month").max = todayISO().slice(0, 7);
  ["month", "f-dept"].forEach((id) => el(id).addEventListener("change", () => load().catch((e) => toast(e.message, "error"))));
  await load();
});
