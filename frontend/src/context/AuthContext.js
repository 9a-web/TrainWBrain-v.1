import React, {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
} from "react";
import {
  authMe,
  authLoginEmail,
  authRegisterEmail,
  authTelegram,
  authGoogleOAuth,
  getGoogleConfig,
  authLogout,
  setAuthToken,
} from "@/api";
import { getTelegram, isTelegram } from "@/lib/platform";

const AuthContext = createContext(null);
const TOKEN_KEY = "twb_token";

function saveToken(token) {
  try {
    if (token) window.localStorage.setItem(TOKEN_KEY, token);
    else window.localStorage.removeItem(TOKEN_KEY);
  } catch (e) {
    /* no-op */
  }
  setAuthToken(token || null);
}

export function AuthProvider({ children }) {
  const [authUser, setAuthUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const u = await authMe();
      setAuthUser(u);
      return u;
    } catch (e) {
      setAuthUser(null);
      return null;
    }
  }, []);

  // Bootstrap: restore an existing session token. The Google callback is
  // handled by the dedicated /auth/google route (see App.js -> GoogleCallback).
  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const token = window.localStorage.getItem(TOKEN_KEY);
        if (token) {
          setAuthToken(token);
          await refresh();
        }
      } catch (e) {
        /* no-op */
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [refresh]);

  const loginEmail = useCallback(async (email, password) => {
    const { token, user } = await authLoginEmail(email, password);
    saveToken(token);
    setAuthUser(user);
    return user;
  }, []);

  const registerEmail = useCallback(async (email, password, name) => {
    const { token, user } = await authRegisterEmail(email, password, name);
    saveToken(token);
    setAuthUser(user);
    return user;
  }, []);

  const loginTelegram = useCallback(async () => {
    const tg = getTelegram();
    const initData = tg && tg.initData;
    if (!initData) throw new Error("Telegram WebApp недоступен");
    const { token, user } = await authTelegram(initData);
    saveToken(token);
    setAuthUser(user);
    return user;
  }, []);

  const loginGoogle = useCallback(async () => {
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    const { client_id } = await getGoogleConfig();
    const redirectUri = window.location.origin + "/auth/google";
    const params = new URLSearchParams({
      client_id,
      redirect_uri: redirectUri,
      response_type: "code",
      scope: "openid email profile",
      access_type: "offline",
      include_granted_scopes: "true",
      prompt: "select_account",
    });
    window.location.href = `https://accounts.google.com/o/oauth2/v2/auth?${params.toString()}`;
  }, []);

  const handleGoogleCode = useCallback(async (code) => {
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    const redirectUri = window.location.origin + "/auth/google";
    const { token, user } = await authGoogleOAuth(code, redirectUri);
    saveToken(token);
    setAuthUser(user);
    return user;
  }, []);

  const logout = useCallback(async () => {
    try {
      await authLogout();
    } catch (e) {
      /* ignore */
    }
    saveToken(null);
    setAuthUser(null);
  }, []);

  return (
    <AuthContext.Provider
      value={{
        authUser,
        loading,
        isAuthenticated: !!authUser,
        isTelegramAvailable: isTelegram(),
        loginEmail,
        registerEmail,
        loginTelegram,
        loginGoogle,
        handleGoogleCode,
        logout,
        refresh,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return (
    useContext(AuthContext) || {
      authUser: null,
      loading: true,
      isAuthenticated: false,
      isTelegramAvailable: false,
    }
  );
}
