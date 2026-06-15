import React, { createContext, useContext, useEffect, useState } from "react";
import { getTelegramAvatar } from "@/api";
import { getEnv, getPlatform } from "@/lib/platform";
import { useAuth } from "@/context/AuthContext";

const UserContext = createContext(null);

export function UserProvider({ children }) {
  const { authUser } = useAuth();
  const [avatarUrl, setAvatarUrl] = useState(null);
  const env = getEnv();
  const platform = getPlatform();

  // The app data key stays `telegram_id` (real for Telegram accounts,
  // synthetic for email/Google) — supplied by the authenticated user.
  const user = authUser
    ? {
        telegram_id: authUser.telegram_id,
        first_name: authUser.first_name,
        last_name: authUser.last_name || null,
        username: authUser.username || null,
        language_code: authUser.language_code || null,
      }
    : null;

  useEffect(() => {
    if (!authUser) {
      setAvatarUrl(null);
      return;
    }
    const fallback = `https://ui-avatars.com/api/?name=${encodeURIComponent(
      authUser.first_name || "U"
    )}&background=FF6B00&color=fff&size=80&bold=true`;
    setAvatarUrl(authUser.picture || fallback);
    // For Telegram accounts, try the live Bot API avatar
    if (env === "telegram" && authUser.telegram_id) {
      getTelegramAvatar(authUser.telegram_id)
        .then((a) => {
          if (a?.avatar_url) setAvatarUrl(a.avatar_url);
        })
        .catch(() => {});
    }
  }, [authUser, env]);

  return (
    <UserContext.Provider
      value={{
        user,
        dbUser: authUser,
        env,
        platform,
        isTelegram: env === "telegram",
        avatarUrl,
        loading: !authUser,
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
