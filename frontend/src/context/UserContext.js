import React, { createContext, useContext, useEffect, useState } from "react";
import { registerUser } from "@/api";

const UserContext = createContext(null);

// Dev-пользователь для разработки/тестов вне Telegram (стабильный telegram_id,
// чтобы назначенные планы сохранялись между сессиями).
const DEV_USER = {
  id: 99000001,
  first_name: "Гость",
  last_name: null,
  username: "dev_user",
  language_code: "ru",
};

export function UserProvider({ children }) {
  const [user, setUser] = useState(null);
  const [dbUser, setDbUser] = useState(null);
  const [isTelegram, setIsTelegram] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const init = async () => {
      let tgUser = null;
      if (window.Telegram?.WebApp) {
        const tg = window.Telegram.WebApp;
        try {
          tg.ready();
          tg.expand();
        } catch (e) {
          // no-op
        }
        tgUser = tg.initDataUnsafe?.user || null;
        setIsTelegram(!!tgUser);
      }

      const effective = tgUser || DEV_USER;
      const normalized = {
        telegram_id: effective.id,
        first_name: effective.first_name,
        last_name: effective.last_name || null,
        username: effective.username || null,
        language_code: effective.language_code || null,
      };
      setUser(normalized);

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
    <UserContext.Provider value={{ user, dbUser, isTelegram, loading }}>
      {children}
    </UserContext.Provider>
  );
}

export function useUser() {
  return (
    useContext(UserContext) || {
      user: null,
      dbUser: null,
      isTelegram: false,
      loading: true,
    }
  );
}
