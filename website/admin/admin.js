/* ========================================================================
   Admin Portal — Alpine.js application logic
   ======================================================================== */

const API_BASE = window.location.origin + "/api/admin";

function getToken() {
  return sessionStorage.getItem("admin_token");
}

function setToken(token) {
  sessionStorage.setItem("admin_token", token);
}

function clearToken() {
  sessionStorage.removeItem("admin_token");
}

async function api(path, opts = {}) {
  const url = API_BASE + path;
  const headers = { "Content-Type": "application/json", ...opts.headers };
  const token = getToken();
  if (token) headers["Authorization"] = "Bearer " + token;

  const resp = await fetch(url, { ...opts, headers });

  if (resp.status === 401 || resp.status === 403) {
    const body = await resp.json().catch(() => ({}));
    if (
      body.detail &&
      (body.detail.includes("Admin 2FA") ||
        body.detail.includes("credentials") ||
        body.detail.includes("expired"))
    ) {
      clearToken();
      window.dispatchEvent(new CustomEvent("admin:logout"));
    }
    throw { status: resp.status, detail: body.detail || "Unauthorized" };
  }

  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw { status: resp.status, detail: body.detail || "Request failed" };
  }

  return resp.json();
}

// ---------------------------------------------------------------------------
// Alpine stores
// ---------------------------------------------------------------------------

document.addEventListener("alpine:init", () => {
  /* ---- Auth store ---- */
  Alpine.store("auth", {
    view: getToken() ? "grid" : "login", // login | twofa | grid
    email: "",
    password: "",
    deliveryMethod: "sms",
    userId: null,
    error: "",
    loading: false,

    get isLoggedIn() {
      return !!getToken();
    },

    async login() {
      this.error = "";
      this.loading = true;
      try {
        const data = await api("/login", {
          method: "POST",
          body: JSON.stringify({
            email: this.email,
            password: this.password,
            delivery_method: this.deliveryMethod,
          }),
        });
        this.userId = data.user_id;
        this.view = "twofa";
      } catch (e) {
        this.error = e.detail || "Login failed";
      } finally {
        this.loading = false;
      }
    },

    async verify(code) {
      this.error = "";
      this.loading = true;
      try {
        const data = await api("/verify-2fa", {
          method: "POST",
          body: JSON.stringify({ user_id: this.userId, code }),
        });
        setToken(data.access_token);
        this.view = "grid";
        Alpine.store("users").load();
      } catch (e) {
        this.error = e.detail || "Verification failed";
      } finally {
        this.loading = false;
      }
    },

    async resend() {
      this.error = "";
      try {
        await api("/resend-code", {
          method: "POST",
          body: JSON.stringify({
            user_id: this.userId,
            delivery_method: this.deliveryMethod,
          }),
        });
        this.error = "";
        alert("Code resent");
      } catch (e) {
        this.error = e.detail || "Failed to resend";
      }
    },

    logout() {
      clearToken();
      this.view = "login";
      this.email = "";
      this.password = "";
      this.userId = null;
      this.error = "";
    },
  });

  /* ---- Users store (grid data) ---- */
  Alpine.store("users", {
    items: [],
    total: 0,
    page: 1,
    perPage: 25,
    pages: 1,
    sort: "name",
    order: "asc",
    search: "",
    statusFilter: "",
    loading: false,
    selectedId: null,

    get rangeText() {
      if (this.total === 0) return "No records";
      const start = (this.page - 1) * this.perPage + 1;
      const end = Math.min(this.page * this.perPage, this.total);
      return `${start}\u2013${end} of ${this.total}`;
    },

    async load() {
      this.loading = true;
      try {
        const params = new URLSearchParams({
          page: this.page,
          per_page: this.perPage,
          sort: this.sort,
          order: this.order,
        });
        if (this.search) params.set("search", this.search);
        if (this.statusFilter) params.set("status", this.statusFilter);

        const data = await api("/users?" + params.toString());
        this.items = data.users;
        this.total = data.total;
        this.pages = data.pages;
        this.page = data.page;
      } catch (e) {
        if (e.detail) console.error("Load failed:", e.detail);
      } finally {
        this.loading = false;
      }
    },

    toggleSort(field) {
      if (this.sort === field) {
        this.order = this.order === "asc" ? "desc" : "asc";
      } else {
        this.sort = field;
        this.order = "asc";
      }
      this.page = 1;
      this.load();
    },

    applySearch() {
      this.page = 1;
      this.load();
    },

    applyFilter() {
      this.page = 1;
      this.load();
    },

    prevPage() {
      if (this.page > 1) {
        this.page--;
        this.load();
      }
    },

    nextPage() {
      if (this.page < this.pages) {
        this.page++;
        this.load();
      }
    },

    selectRow(id) {
      this.selectedId = id;
      Alpine.store("detail").open(id);
    },
  });

  /* ---- Detail modal store ---- */
  Alpine.store("detail", {
    visible: false,
    loading: false,
    saving: false,
    user: null,
    editing: false,
    editData: {},
    tab: "profile",
    error: "",

    async open(id) {
      this.visible = true;
      this.loading = true;
      this.editing = false;
      this.error = "";
      this.tab = "profile";
      try {
        this.user = await api("/users/" + id);
        this._initEditData();
      } catch (e) {
        this.error = e.detail || "Failed to load user";
      } finally {
        this.loading = false;
      }
    },

    close() {
      this.visible = false;
      this.user = null;
      Alpine.store("users").selectedId = null;
    },

    startEdit() {
      this._initEditData();
      this.editing = true;
    },

    cancelEdit() {
      this.editing = false;
    },

    _initEditData() {
      if (!this.user) return;
      this.editData = {
        name: this.user.name,
        email: this.user.email,
        phone: this.user.phone || "",
        isActive: this.user.isActive,
        roles: (this.user.roles || []).join(", "),
        generation_credits: this.user.generation_credits,
        max_credits: this.user.max_credits,
        super_user: this.user.super_user || false,
      };
    },

    async save() {
      this.error = "";
      this.saving = true;
      try {
        const body = {
          name: this.editData.name,
          email: this.editData.email,
          phone: this.editData.phone || null,
          isActive: this.editData.isActive,
          roles: this.editData.roles
            .split(",")
            .map((r) => r.trim())
            .filter(Boolean),
          generation_credits: parseInt(this.editData.generation_credits, 10) || 0,
          max_credits: parseInt(this.editData.max_credits, 10) || 10,
          super_user: this.editData.super_user,
        };
        this.user = await api("/users/" + this.user.id, {
          method: "PUT",
          body: JSON.stringify(body),
        });
        this.editing = false;
        Alpine.store("users").load();
      } catch (e) {
        this.error = e.detail || "Save failed";
      } finally {
        this.saving = false;
      }
    },

    async archive() {
      if (!confirm("Archive this user? They will be deactivated.")) return;
      this.saving = true;
      try {
        this.user = await api("/users/" + this.user.id + "/archive", {
          method: "PUT",
        });
        Alpine.store("users").load();
      } catch (e) {
        this.error = e.detail || "Archive failed";
      } finally {
        this.saving = false;
      }
    },

    async unarchive() {
      this.saving = true;
      try {
        this.user = await api("/users/" + this.user.id + "/unarchive", {
          method: "PUT",
        });
        Alpine.store("users").load();
      } catch (e) {
        this.error = e.detail || "Unarchive failed";
      } finally {
        this.saving = false;
      }
    },
  });

  /* ---- Sub-modal store (preferences / JSON editor) ---- */
  Alpine.store("submodal", {
    visible: false,
    title: "",
    jsonText: "",
    field: "",
    error: "",
    saving: false,

    openJson(title, field) {
      const detail = Alpine.store("detail");
      if (!detail.user) return;
      const value = detail.user[field];
      this.title = title;
      this.field = field;
      this.jsonText = JSON.stringify(value, null, 2) || "{}";
      this.error = "";
      this.visible = true;
    },

    close() {
      this.visible = false;
    },

    async save() {
      this.error = "";
      let parsed;
      try {
        parsed = JSON.parse(this.jsonText);
      } catch {
        this.error = "Invalid JSON";
        return;
      }
      this.saving = true;
      const detail = Alpine.store("detail");
      try {
        const body = {};
        body[this.field] = parsed;
        detail.user = await api("/users/" + detail.user.id, {
          method: "PUT",
          body: JSON.stringify(body),
        });
        this.visible = false;
        Alpine.store("users").load();
      } catch (e) {
        this.error = e.detail || "Save failed";
      } finally {
        this.saving = false;
      }
    },
  });

  // Auto-load users if token exists on page load
  if (getToken()) {
    Alpine.store("users").load();
  }

  // Handle forced logout events
  window.addEventListener("admin:logout", () => {
    Alpine.store("auth").logout();
  });
});

// ---------------------------------------------------------------------------
// Helper functions used in templates
// ---------------------------------------------------------------------------

function formatDate(val) {
  if (!val) return "\u2014";
  const d = new Date(val);
  if (isNaN(d.getTime())) return "\u2014";
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function subStatusClass(status) {
  if (!status) return "badge-sub-free";
  const s = status.toLowerCase();
  if (s === "active" || s === "trialing") return "badge-sub-active";
  if (s === "canceled" || s === "past_due" || s === "unpaid") return "badge-sub-canceled";
  return "badge-sub-free";
}
