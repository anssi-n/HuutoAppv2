/* Account UI: token storage, session resolution, and the account dialogs.
   The backend only reads the Authorization header (OAuth2PasswordBearer,
   auth.py), so every call goes through apiFetch() which attaches the token.
   On 401 the stored token is dropped and the UI falls back to logged out. */

const TOKEN_KEY = "huutoapp-token";
const USERS_URL = "/api/v1/users";

const getToken = () => localStorage.getItem(TOKEN_KEY);

function setToken(token) {
    localStorage.setItem(TOKEN_KEY, token);
}

function clearToken() {
    localStorage.removeItem(TOKEN_KEY);
}

function errorMessage(data, status) {
    if (!data) return `server returned HTTP ${status}`;
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail)) return data.detail.map((d) => d.msg).join(", ");
    return JSON.stringify(data);
}

/* Set by the UI below; apiFetch lives outside that scope but must be able to
   drop the user back to the logged out state on an expired token. */
let sessionExpiredHandler = null;

async function apiFetch(path, options = {}) {
    const headers = new Headers(options.headers || {});
    const token = getToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
    if (options.body !== undefined && !(options.body instanceof URLSearchParams)) {
        headers.set("Content-Type", "application/json");
    }

    const response = await fetch(path, { ...options, headers });
    if (response.status === 401) {
        clearToken();
        if (sessionExpiredHandler) {
            sessionExpiredHandler("Your session has expired. Please sign in again.");
        }
    }
    return response;
}

function setStatus(element, message, isError) {
    if (!element) return;
    element.textContent = message;
    element.classList.toggle("error", Boolean(isError));
}

function setFieldError(form, name, message) {
    const field = form.elements[name];
    const errorEl = form.querySelector(`[data-error-for="${name}"]`);
    if (field) field.classList.toggle("invalid", Boolean(message));
    if (errorEl) errorEl.textContent = message || "";
}

function clearFieldErrors(form) {
    for (const field of form.querySelectorAll("[id$='-error']")) {
        field.textContent = "";
    }
    for (const el of form.querySelectorAll(".invalid")) {
        el.classList.remove("invalid");
    }
}

const disableForm = (form, button, busy, busyText) => {
    const original = button.textContent;
    button.disabled = busy;
    button.textContent = busy ? busyText : original;
    for (const el of form.elements) {
        if (el !== button) el.disabled = busy;
    }
};

(() => {
    const accountBtn = document.getElementById("account-btn");
    const accountName = document.getElementById("account-name");
    const actions = document.getElementById("account-actions");
    const anon = document.getElementById("account-anon");
    const deleteAccountName = document.getElementById("delete-account-name");
    const menu = document.getElementById("account-menu");
    const loginDialog = document.getElementById("login-dialog");
    const registerDialog = document.getElementById("register-dialog");
    const profileDialog = document.getElementById("profile-dialog");
    const deleteAccountDialog = document.getElementById("delete-account-dialog");

    if (!accountBtn || !loginDialog || !registerDialog || !profileDialog || !deleteAccountDialog) return;

    let currentUser = null;

    const openDialog = (dialog) => {
        if (dialog && !dialog.open) dialog.showModal();
    };

    function onLoggedOut(message) {
        currentUser = null;
        // No admin role, so the admin-only controls stay hidden.
        delete document.documentElement.dataset.role;
        if (actions) actions.hidden = true;
        if (anon) anon.hidden = false;
        if (accountBtn) {
            accountBtn.hidden = false;
            accountBtn.setAttribute("aria-label", "Account");
            accountBtn.setAttribute("title", "Account");
        }
        if (accountName) accountName.textContent = "";
        if (deleteAccountName) deleteAccountName.textContent = "";
        if (menu) menu.hidden = true;
        if (message) setStatus(document.getElementById("account-status"), message, true);
    }

    sessionExpiredHandler = onLoggedOut;

    function onLoggedIn(user) {
        currentUser = user;
        // Drives the admin-only controls via html:not([data-role="admin"]).
        if (user && user.role) {
            document.documentElement.dataset.role = user.role;
        } else {
            delete document.documentElement.dataset.role;
        }
        if (accountName) accountName.textContent = user.username;
        if (deleteAccountName) deleteAccountName.textContent = user.username;
        if (accountBtn) {
            accountBtn.hidden = false;
            accountBtn.setAttribute("aria-label", `Account: ${user.username}`);
            accountBtn.setAttribute("title", `Account: ${user.username}`);
        }
        if (actions) actions.hidden = false;
        if (anon) anon.hidden = true;
        setStatus(document.getElementById("account-status"), "");
    }

    /* ---------- login ---------- */
    const loginForm = document.getElementById("login-form");
    const loginEmail = document.getElementById("login-email");
    const loginStatus = document.getElementById("login-status");
    const loginSubmit = document.getElementById("login-submit");

    const prefillLogin = (email) => {
        if (loginEmail && email) loginEmail.value = email;
        setStatus(loginStatus, "", false);
    };

    loginForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (loginSubmit.disabled) return;
        clearFieldErrors(loginForm);
        setStatus(loginStatus, "", false);

        const email = String(loginForm.elements.email.value || "").trim();
        const password = String(loginForm.elements.password.value || "");
        let firstInvalid = null;
        if (!email) {
            setFieldError(loginForm, "email", "Enter your email address.");
            firstInvalid = firstInvalid || loginForm.elements.email;
        }
        if (!password) {
            setFieldError(loginForm, "password", "Enter your password.");
            firstInvalid = firstInvalid || loginForm.elements.password;
        }
        if (firstInvalid) {
            firstInvalid.focus();
            return;
        }

        disableForm(loginForm, loginSubmit, true, "Signing in…");
        try {
            // OAuth2PasswordRequestForm expects form encoding, not JSON.
            const response = await apiFetch(`${USERS_URL}/token`, {
                method: "POST",
                body: new URLSearchParams({ username: email, password }),
            });
            const data = await response.json().catch(() => null);
            if (!response.ok) {
                throw new Error(errorMessage(data, response.status));
            }
            setToken(data.access_token);
            loginForm.elements.password.value = "";
            loginDialog.close();
            const me = await apiFetch(`${USERS_URL}/me`);
            if (!me.ok) throw new Error("Signed in, but could not load your account.");
            onLoggedIn(await me.json());
        } catch (err) {
            setStatus(loginStatus, err.message, true);
        } finally {
            disableForm(loginForm, loginSubmit, false, "Signing in…");
        }
    });

    /* ---------- register ---------- */
    const registerForm = document.getElementById("register-form");
    const registerStatus = document.getElementById("register-status");
    const registerSubmit = document.getElementById("register-submit");

    registerForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (registerSubmit.disabled) return;
        clearFieldErrors(registerForm);
        setStatus(registerStatus, "", false);

        const username = String(registerForm.elements.username.value || "").trim();
        const email = String(registerForm.elements.email.value || "").trim();
        const password = String(registerForm.elements.password.value || "");
        let firstInvalid = null;
        if (username.length < 1 || username.length > 50) {
            setFieldError(registerForm, "username", "Enter a username (1-50 characters).");
            firstInvalid = firstInvalid || registerForm.elements.username;
        }
        if (!email) {
            setFieldError(registerForm, "email", "Enter your email address.");
            firstInvalid = firstInvalid || registerForm.elements.email;
        }
        if (password.length < 8) {
            setFieldError(registerForm, "password", "Enter a password of at least 8 characters.");
            firstInvalid = firstInvalid || registerForm.elements.password;
        }
        if (firstInvalid) {
            firstInvalid.focus();
            return;
        }

        disableForm(registerForm, registerSubmit, true, "Creating account…");
        try {
            const response = await apiFetch(USERS_URL, {
                method: "POST",
                body: JSON.stringify({ username, email, password }),
            });
            const data = await response.json().catch(() => null);
            if (!response.ok) {
                throw new Error(errorMessage(data, response.status));
            }
            // Registration does not sign the user in; hand off to the login form.
            registerForm.reset();
            clearFieldErrors(registerForm);
            registerDialog.close();
            prefillLogin(email);
            openDialog(loginDialog);
        } catch (err) {
            setStatus(registerStatus, err.message, true);
        } finally {
            disableForm(registerForm, registerSubmit, false, "Creating account…");
        }
    });

    /* ---------- edit profile ---------- */
    const profileForm = document.getElementById("profile-form");
    const profileStatus = document.getElementById("profile-status");
    const profileSubmit = document.getElementById("profile-submit");

    profileForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (profileSubmit.disabled || !currentUser) return;
        clearFieldErrors(profileForm);
        setStatus(profileStatus, "", false);

        const username = String(profileForm.elements.username.value || "").trim();
        const email = String(profileForm.elements.email.value || "").trim();
        let firstInvalid = null;
        if (username.length < 1 || username.length > 50) {
            setFieldError(profileForm, "username", "Enter a username (1-50 characters).");
            firstInvalid = firstInvalid || profileForm.elements.username;
        }
        if (!email) {
            setFieldError(profileForm, "email", "Enter your email address.");
            firstInvalid = firstInvalid || profileForm.elements.email;
        }
        if (firstInvalid) {
            firstInvalid.focus();
            return;
        }

        disableForm(profileForm, profileSubmit, true, "Saving…");
        try {
            const response = await apiFetch(`${USERS_URL}/${currentUser.id}`, {
                method: "PATCH",
                body: JSON.stringify({ username, email }),
            });
            const data = await response.json().catch(() => null);
            if (!response.ok) {
                throw new Error(errorMessage(data, response.status));
            }
            // Details changed, so drop the token and return to the logged out state.
            clearToken();
            profileForm.reset();
            profileDialog.close();
            onLoggedOut("Your details were updated. Please sign in again.");
        } catch (err) {
            setStatus(profileStatus, err.message, true);
        } finally {
            disableForm(profileForm, profileSubmit, false, "Saving…");
        }
    });

    /* ---------- delete account ---------- */
    const deleteAccountForm = document.getElementById("delete-account-form");
    const deleteAccountStatus = document.getElementById("delete-account-status");
    const deleteAccountSubmit = document.getElementById("delete-account-submit");

    deleteAccountForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (deleteAccountSubmit.disabled || !currentUser) return;
        setStatus(deleteAccountStatus, "", false);

        disableForm(deleteAccountForm, deleteAccountSubmit, true, "Deleting…");
        try {
            const response = await apiFetch(`${USERS_URL}/${currentUser.id}`, { method: "DELETE" });
            if (!response.ok) {
                throw new Error(errorMessage(await response.json().catch(() => null), response.status));
            }
            clearToken();
            deleteAccountDialog.close();
            onLoggedOut("Your account was deleted.");
        } catch (err) {
            setStatus(deleteAccountStatus, err.message, true);
        } finally {
            disableForm(deleteAccountForm, deleteAccountSubmit, false, "Deleting…");
        }
    });

    /* ---------- account menu ---------- */
    let menuOpen = false;

    const closeMenu = () => {
        if (!menu) return;
        menu.hidden = true;
        menuOpen = false;
        accountBtn.setAttribute("aria-expanded", "false");
    };

    const openMenu = () => {
        if (!menu) return;
        menu.hidden = false;
        menuOpen = true;
        accountBtn.setAttribute("aria-expanded", "true");
        const first = menu.querySelector("button, a");
        if (first) first.focus();
    };

    accountBtn.addEventListener("click", () => {
        if (menuOpen) closeMenu();
        else openMenu();
    });

    document.addEventListener("click", (event) => {
        if (!menuOpen) return;
        if (menu.contains(event.target) || accountBtn.contains(event.target)) return;
        closeMenu();
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && menuOpen) closeMenu();
    });

    for (const item of menu.querySelectorAll("[data-account-action]")) {
        item.addEventListener("click", () => {
            closeMenu();
            const action = item.dataset.accountAction;
            if (action === "login") openDialog(loginDialog);
            else if (action === "register") openDialog(registerDialog);
            else if (action === "edit") {
                profileForm.elements.username.value = currentUser ? currentUser.username : "";
                profileForm.elements.email.value = currentUser ? currentUser.email : "";
                clearFieldErrors(profileForm);
                setStatus(profileStatus, "", false);
                openDialog(profileDialog);
            } else if (action === "delete") {
                setStatus(deleteAccountStatus, "", false);
                openDialog(deleteAccountDialog);
            } else if (action === "logout") {
                clearToken();
                onLoggedOut("You have been signed out.");
            }
        });
    }

    document.getElementById("login-switch").addEventListener("click", (event) => {
        event.preventDefault();
        registerDialog.close();
        openDialog(loginDialog);
    });
    document.getElementById("register-switch").addEventListener("click", (event) => {
        event.preventDefault();
        loginDialog.close();
        openDialog(registerDialog);
    });
    document.getElementById("register-open").addEventListener("click", (event) => {
        event.preventDefault();
        closeMenu();
        registerForm.reset();
        clearFieldErrors(registerForm);
        setStatus(registerStatus, "", false);
        openDialog(registerDialog);
    });
    document.getElementById("login-open").addEventListener("click", (event) => {
        event.preventDefault();
        closeMenu();
        prefillLogin("");
        openDialog(loginDialog);
    });

    for (const dialog of [loginDialog, registerDialog, profileDialog, deleteAccountDialog]) {
        dialog.addEventListener("close", () => {
            clearFieldErrors(dialog.querySelector("form"));
        });
    }

    /* ---------- restore session ---------- */
    (async () => {
        // No token means the anonymous menu, so the account button must be shown.
        if (!getToken()) {
            onLoggedOut();
            return;
        }
        try {
            const response = await apiFetch(`${USERS_URL}/me`);
            if (response.status === 401) return;
            if (!response.ok) throw new Error(`server returned HTTP ${response.status}`);
            onLoggedIn(await response.json());
        } catch (err) {
            console.error("Unable to restore session", err);
            onLoggedOut();
        }
    })();
})();
