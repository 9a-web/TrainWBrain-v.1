import React, { createContext, useContext, useEffect, useState } from "react";
import { registerUser, getTelegramAvatar } from "@/api";
import {
  getEnv,
  getPlatform,
  getTelegramUser,
  getOrCreateWebUser,
} from "@/lib/platform";

const UserContext = createContext(null);

export function UserProvider({ children }) {
  const [user, setUser] = useState(null);
  const [dbUser, setDbUser] = useState(null);
  const [env, setEnv] = useState("web"); // "telegram" | "pwa" | "web"
  const [platform, setPlatform] = useState("web");
  const [avatarUrl, setAvatarUrl] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const init = async () => {
      const currentEnv = getEnv();
      setEnv(currentEnv);
      setPlatform(getPlatform());

      // Identity: real Telegram user inside Telegram, otherwise a stable
      // per-browser web guest (persisted in localStorage) so data survives.
      const tgUser = getTelegramUser();
      const effective = tgUser || getOrCreateWebUser();
      const normalized = {
        telegram_id: effective.id,
        first_name: effective.first_name,
        last_name: effective.last_name || null,
        username: effective.username || null,
        language_code: effective.language_code || null,
      };
      setUser(normalized);

      // Avatar: placeholder first, then try Telegram Bot API
      const fallback = `https://ui-avatars.com/api/?name=${encodeURIComponent(
        normalized.first_name || "U"
      )}&background=FF6B00&color=fff&size=80&bold=true`;
      setAvatarUrl(effective.photo_url || fallback);
      getTelegramAvatar(normalized.telegram_id)
        .then((a) => {
          if (a?.avatar_url) setAvatarUrl(a.avatar_url);
        })
        .catch(() => {});

      try {
        const db = await registerUser(normalized);
        setDbUser(db);
      } catch (e) {
        console.error("registerUser failed", e);
      }
      setLoading(false);
    };

    init();
  }, []);

  return (
    <UserContext.Provider
      value={{
        user,
        dbUser,
        env,
        platform,
        isTelegram: env === "telegram",
        avatarUrl,
        loading,
      }}
    >
      {children}
    </UserContext.Provider>
  );
}

export function useUser() {
  return (
    useContext(UserContext) || {
      user: null,
      dbUser: null,
      env: "web",
      platform: "web",
      isTelegram: false,
      avatarUrl: null,
      loading: true,
    }
  );
}
