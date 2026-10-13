/* Shared helpers: API access, layout, dialogs, toasts, formatting. */
"use strict";

const STATUS_LABELS = {
  present: "Present", late: "Late", half_day: "Half day", absent: "Absent", on_leave: "On leave",
};
const LEAVE_TYPES = { annual: "Annual", sick: "Sick", casual: "Casual", unpaid: "Unpaid", other: "Other" };

const ICONS = {
  dashboard: '<path d="M3 13h8V3H3zm0 8h8v-6H3zm10 0h8V11h-8zm0-18v6h8V3z"/>',
  employees: '<path d="M16 11a4 4 0 1 0-4-4 4 4 0 0 0 4 4zm-8 0a3 3 0 1 0-3-3 3 3 0 0 0 3 3zm0 2c-2.3 0-7 1.2-7 3.5V19h7v-2.5c0-.9.4-1.8 1.1-2.5A11 11 0 0 0 8 13zm8 0c-2.7 0-8 1.3-8 4v2h16v-2c0-2.7-5.3-4-8-4z"/>',
  departments: '<path d="M12 7V3H2v18h20V7zM6 19H4v-2h2zm0-4H4v-2h2zm0-4H4V9h2zm0-4H4V5h2zm4 12H8v-2h2zm0-4H8v-2h2zm0-4H8V9h2zm0-4H8V5h2zm10 12h-8v-2h2v-2h-2v-2h2v-2h-2V9h8z"/>',
  attendance: '<path d="M19 4h-1V2h-2v2H8V2H6v2H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2zm0 16H5V9h14zm-8.5-2.5-3.5-3.5 1.4-1.4 2.1 2.1 4.6-4.6 1.4 1.4z"/>',
  leaves: '<path d="M17 12h-5v5h5zM16 1v2H8V1H6v2H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V5a2 2 0 0 0-2-2h-1V1zm3 18H5V8h14z"/>',
  reports: '<path d="M19 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V5a2 2 0 0 0-2-2zM9 17H7v-7h2zm4 0h-2V7h2zm4 0h-2v-4h2z"/>',
  users: '<path d="M12 1 3 5v6c0 5.5 3.8 10.7 9 12 5.2-1.3 9-6.5 9-12V5zm0 6a2.5 2.5 0 1 1-2.5 2.5A2.5 2.5 0 0 1 12 7zm5 10H7v-1c0-1.7 3.3-2.5 5-2.5s5 .8 5 2.5z"/>',
  menu: '<path d="M3 6h18v2H3zm0 5h18v2H3zm0 5h18v2H3z"/>',
};

const NAV = [
  { href: "/", label: "Dashboard", icon: "dashboard" },
  { href: "/employees", label: "Employees", icon: "employees" },
  { href: "/departments", label: "Departments", icon: "departments" },
  { href: "/attendance", label: "Attendance", icon: "attendance" },
  { href: "/leaves", label: "Leave records", icon: "leaves" },
  { href: "/reports", label: "Monthly reports", icon: "reports" },
  { href: "/users", label: "System users", icon: "users", admin: true },
];

/* ---------- escaping & formatting ---------- */
function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function icon(name) {
  return `<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">${ICONS[name]}</svg>`;
}

function badge(value, label) {
  return `<span class="badge ${esc(value)}">${esc(label ?? value)}</span>`;
}

function statusBadge(status) {
  return status ? badge(status, STATUS_LABELS[status]) : badge("none", "Not marked");
}

function todayISO() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function fmtDate(iso, opts = { day: "numeric", month: "short", year: "numeric" }) {
  if (!iso) return "";
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(undefined, opts);
}

function fmtRate(rate) {
  return rate === null || rate === undefined ? "—" : `${rate}%`;
}

function debounce(fn, ms = 250) {
  let t;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}

/* ---------- API ---------- */
class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status; }
}

function errorMessage(detail) {
  if (!detail) return "Request failed";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((d) => {
      const field = (d.loc || []).filter((p) => p !== "body" && typeof p === "string").join(".");
      const msg = String(d.msg || "").replace(/^Value error, /, "");
      return field ? `${field.replace(/_/g, " ")}: ${msg}` : msg;
    }).join("; ");
  }
  return JSON.stringify(detail);
}

async function api(path, { method = "GET", body } = {}) {
  const opts = { method, headers: { Accept: "application/json" }, credentials: "same-origin" };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(path, opts);
  if (res.status === 401 && !path.startsWith("/api/auth/login")) {
    window.location.href = "/login";
    throw new ApiError("Session expired", 401);
  }
  const data = res.headers.get("content-type")?.includes("application/json") ? await res.json() : null;
  if (!res.ok) throw new ApiError(errorMessage(data?.detail), res.status);
  return data;
}

function qs(params) {
  const p = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => { if (v !== "" && v !== null && v !== undefined) p.set(k, v); });
  const s = p.toString();
  return s ? `?${s}` : "";
}

/* ---------- toasts ---------- */
function toast(message, type = "info") {
  let box = document.querySelector(".toasts");
  if (!box) {
    box = document.createElement("div");
    box.className = "toasts";
    box.setAttribute("role", "status");
    box.setAttribute("aria-live", "polite");
    document.body.appendChild(box);
  }
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.textContent = message;
  box.appendChild(el);
  setTimeout(() => el.remove(), type === "error" ? 6000 : 3500);
}

/* ---------- layout ---------- */
let CURRENT_USER = null;

async function initLayout() {
  const user = await api("/api/auth/me");
  CURRENT_USER = user;
  const path = window.location.pathname;
  const sidebar = document.getElementById("sidebar");
  const links = NAV.filter((n) => !n.admin || user.role === "admin").map((n) =>
    `<a href="${n.href}"${n.href === path ? ' aria-current="page"' : ""}>${icon(n.icon)}<span>${esc(n.label)}</span></a>`
  ).join("");
  sidebar.innerHTML = `
    <div class="brand"><span class="brand-mark">EA</span><span>EAMS</span></div>
    <nav class="nav" aria-label="Main">${links}</nav>
    <div class="sidebar-foot">
      <div class="who">${esc(user.full_name)}</div>
      <div class="role">${esc(user.role === "admin" ? "Administrator" : "HR")}</div>
      <div class="links"><a href="/account">Account</a><button type="button" class="linklike" id="logout-btn">Log out</button></div>
    </div>`;

  const top = document.createElement("header");
  top.className = "topbar";
  top.innerHTML = `<div class="brand"><span class="brand-mark">EA</span><span>EAMS</span></div>
    <button type="button" class="icon-btn" id="menu-btn" aria-label="Open menu" aria-expanded="false">
      <svg viewBox="0 0 24 24" width="24" height="24" fill="currentColor" aria-hidden="true">${ICONS.menu}</svg></button>`;
  document.querySelector(".layout").prepend(top);

  const menuBtn = document.getElementById("menu-btn");
  menuBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    const open = document.body.classList.toggle("nav-open");
    menuBtn.setAttribute("aria-expanded", String(open));
  });
  document.addEventListener("click", (e) => {
    if (document.body.classList.contains("nav-open") && !sidebar.contains(e.target)) {
      document.body.classList.remove("nav-open");
      menuBtn.setAttribute("aria-expanded", "false");
    }
  });
  document.getElementById("logout-btn").addEventListener("click", async () => {
    try { await api("/api/auth/logout", { method: "POST" }); } finally { window.location.href = "/login"; }
  });
  return user;
}

/* ---------- forms & dialogs ---------- */
function formValues(form) {
  const out = {};
  for (const el of form.elements) {
    if (!el.name || el.disabled) continue;
    if (el.type === "checkbox") out[el.name] = el.checked;
    else if (el.dataset.type === "int") out[el.name] = el.value === "" ? null : Number(el.value);
    else out[el.name] = el.value;
  }
  return out;
}

function fillForm(form, data) {
  for (const el of form.elements) {
    if (!el.name || !(el.name in data)) continue;
    const v = data[el.name];
    if (el.type === "checkbox") el.checked = Boolean(v);
    else el.value = v ?? "";
  }
}

function showFormError(form, message) {
  const box = form.querySelector(".form-error");
  if (!box) return toast(message, "error");
  box.textContent = message;
  box.classList.toggle("hidden", !message);
}

/** Wire a <dialog> form: onSubmit(values) may throw ApiError; on success the dialog closes. */
function bindDialog(dialog, onSubmit) {
  const form = dialog.querySelector("form");
  dialog.querySelectorAll("[data-close]").forEach((b) => b.addEventListener("click", () => dialog.close()));
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = form.querySelector('button[type="submit"]');
    btn.disabled = true;
    showFormError(form, "");
    try {
      await onSubmit(formValues(form));
      dialog.close();
    } catch (err) {
      showFormError(form, err.message);
    } finally {
      btn.disabled = false;
    }
  });
  return {
    open(title, data = {}) {
      dialog.querySelector(".dialog-title").textContent = title;
      form.reset();
      fillForm(form, data);
      showFormError(form, "");
      dialog.showModal();
      form.querySelector("input:not([type=hidden]):not([disabled]), select, textarea")?.focus();
    },
    form,
  };
}

/** Promise-based confirm dialog (avoids blocking window.confirm). */
function confirmDialog(message, { okLabel = "Delete", danger = true } = {}) {
  return new Promise((resolve) => {
    const d = document.createElement("dialog");
    d.innerHTML = `<form method="dialog">
      <div class="dialog-head"><h2>Please confirm</h2></div>
      <div class="dialog-body"><p></p></div>
      <div class="dialog-foot">
        <button class="btn" value="cancel">Cancel</button>
        <button class="btn ${danger ? "danger" : "primary"}" value="ok">${esc(okLabel)}</button>
      </div></form>`;
    d.querySelector("p").textContent = message;
    document.body.appendChild(d);
    d.addEventListener("close", () => { resolve(d.returnValue === "ok"); d.remove(); });
    d.showModal();
  });
}

/* ---------- options ---------- */
async function loadDepartmentOptions(select, { includeAll = false, allLabel = "All departments" } = {}) {
  const depts = await api("/api/departments");
  select.innerHTML = (includeAll ? `<option value="">${esc(allLabel)}</option>` : '<option value="">Select department</option>')
    + depts.map((d) => `<option value="${d.id}">${esc(d.name)}</option>`).join("");
  return depts;
}

/* ---------- chart tooltip ---------- */
const tooltip = {
  el: null,
  show(html, x, y) {
    if (!this.el) {
      this.el = document.createElement("div");
      this.el.className = "tooltip";
      this.el.setAttribute("role", "tooltip");
      document.body.appendChild(this.el);
    }
    this.el.innerHTML = html;
    this.el.classList.remove("hidden");
    const r = this.el.getBoundingClientRect();
    const left = Math.min(Math.max(8, x - r.width / 2), window.innerWidth - r.width - 8);
    const top = y - r.height - 12 < 8 ? y + 16 : y - r.height - 12;
    this.el.style.left = `${left}px`;
    this.el.style.top = `${top}px`;
  },
  hide() { this.el?.classList.add("hidden"); },
};

function attachTooltip(el, html) {
  const showAt = (x, y) => tooltip.show(html, x, y);
  el.addEventListener("mousemove", (e) => showAt(e.clientX, e.clientY));
  el.addEventListener("mouseleave", () => tooltip.hide());
  el.addEventListener("focus", () => { const r = el.getBoundingClientRect(); showAt(r.left + r.width / 2, r.top); });
  el.addEventListener("blur", () => tooltip.hide());
}

function onReady(fn) {
  const run = () => fn().catch((err) => { if (err.status !== 401) toast(err.message, "error"); });
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", run);
  else run();
}
