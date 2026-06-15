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
  authGoogleSession,
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

  // Bootstrap: handle Google (Emergent) callback first, then existing session.
  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const hash = window.location.hash || "";
        if (hash.includes("session_id=")) {
          const sid = new URLSearchParams(hash.replace(/^#/, "")).get("session_id");
          // Clean the URL fragment regardless of outcome
          window.history.replaceState(
            null,
            "",
            window.location.pathname + window.location.search
          );
          if (sid) {
            try {
              const { token, user } = await authGoogleSession(sid);
              if (!active) return;
              saveToken(token);
              setAuthUser(user);
              setLoading(false);
              return;
            } catch (e) {
              /* fall through to normal session check */
            }
          }
        }
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

  const loginGoogle = useCallback(() => {
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    const redirectUrl = window.location.origin + "/";
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(
      redirectUrl
    )}`;
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
