/**
 * Shows the signed-in account and arms the sign-out button.
 *
 * The sign-out form posts a token that the server issued for this session.
 * Without it, another site could make a signed-in browser submit the form and
 * sign the reader out. The token is fetched here rather than written into the
 * page, because the page itself is a static file.
 */

const ACCOUNT_LABEL_ID = "signed-in-account";
const SIGN_OUT_TOKEN_FIELD_ID = "sign-out-token";
const SESSION_ENDPOINT = "/api/session";
const LOGIN_PATH = "/login";

async function loadSession() {
    const response = await fetch(SESSION_ENDPOINT);
    if (response.status === 401) {
        window.location.assign(LOGIN_PATH);
        return;
    }
    if (!response.ok) {
        return;
    }

    const session = await response.json();
    const accountLabel = document.getElementById(ACCOUNT_LABEL_ID);
    if (accountLabel && session.username) {
        accountLabel.textContent = session.username;
    }

    const tokenField = document.getElementById(SIGN_OUT_TOKEN_FIELD_ID);
    if (tokenField) {
        tokenField.value = session.sign_out_token || "";
    }
}

loadSession();
