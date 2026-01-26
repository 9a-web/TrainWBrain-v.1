import { useEffect, useState } from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import axios from "axios";
import DateSelector from "@/components/DateSelector";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const Home = () => {
  const [telegramUser, setTelegramUser] = useState(null);
  const [avatarUrl, setAvatarUrl] = useState(null);
  const [dbUser, setDbUser] = useState(null);

  // Регистрация/обновление пользователя в БД
  const registerUser = async (tgUser) => {
    try {
      const response = await axios.post(`${API}/users`, {
        telegram_id: tgUser.id,
        first_name: tgUser.first_name,
        last_name: tgUser.last_name || null,
        username: tgUser.username || null,
        language_code: tgUser.language_code || null
      });
      setDbUser(response.data);
      console.log('User registered/updated:', response.data);
      return response.data;
    } catch (error) {
      console.error('Failed to register user:', error);
      return null;
    }
  };

  // Загрузка аватара через Backend API (Telegram Bot API)
  const loadAvatar = async (userId, firstName) => {
    try {
      const response = await axios.get(`${API}/telegram/avatar/${userId}`);
      if (response.data?.avatar_url) {
        setAvatarUrl(response.data.avatar_url);
      } else {
        // Fallback на UI Avatars
        setAvatarUrl(getDefaultAvatar(firstName));
      }
    } catch (error) {
      console.error('Failed to load avatar:', error);
      setAvatarUrl(getDefaultAvatar(firstName));
    }
  };

  // Генерация дефолтного аватара
  const getDefaultAvatar = (name) => {
    const displayName = name || 'User';
    return `https://ui-avatars.com/api/?name=${encodeURIComponent(displayName)}&background=FF6B00&color=fff&size=80&bold=true`;
  };

  useEffect(() => {
    // Инициализация Telegram WebApp
    if (window.Telegram?.WebApp) {
      const tg = window.Telegram.WebApp;
      tg.ready();
      tg.expand();
      
      const user = tg.initDataUnsafe?.user;
      if (user) {
        setTelegramUser(user);
        // Регистрируем пользователя в БД
        await registerUser(user);
        // Загружаем аватар через API
        loadAvatar(user.id, user.first_name);
      } else {
        // Нет данных пользователя - дефолтный аватар
        setAvatarUrl(getDefaultAvatar('Гость'));
      }
    } else {
      // Не в Telegram - дефолтный аватар
      setAvatarUrl(getDefaultAvatar('Гость'));
    }
  }, []);

  // Получить URL аватара
  const getAvatarUrl = () => {
    return avatarUrl || getDefaultAvatar(telegramUser?.first_name);
  };

  // Get greeting and icon based on current time
  const getGreetingData = () => {
    const hour = new Date().getHours();
    if (hour >= 5 && hour < 12) {
      return { text: 'Доброе утро', icon: '/sunrise.svg' };
    } else if (hour >= 12 && hour < 18) {
      return { text: 'Добрый день', icon: '/day.svg' };
    } else if (hour >= 18 && hour < 23) {
      return { text: 'Добрый вечер', icon: '/sunset.svg' };
    } else {
      return { text: 'Доброй ночи', icon: '/night.svg' };
    }
  };

  const greetingData = getGreetingData();

  return (
    <div className="app-container" data-testid="main-container">
      {/* Gradient Background with Blur Effect */}
      <div className="gradient-background" data-testid="gradient-background">
        <img 
          src="/gradientcenter.png" 
          alt="" 
          aria-hidden="true"
        />
      </div>
      
      {/* Content Layer */}
      <div className="content-layer" data-testid="content-layer">
        {/* Header */}
        <header className="header" data-testid="header">
          {/* Logo */}
          <div className="header-logo" data-testid="header-logo">
            <img src="/TWBlogo.png" alt="TrainWithBrain" />
          </div>
          
          {/* Right side: Menu & Profile */}
          <div className="header-right" data-testid="header-right">
            <button 
              className="menu-button" 
              data-testid="menu-button"
              aria-label="Open menu"
            >
              <img src="/menu.svg" alt="Menu" width={40} height={40} />
            </button>
            
            <img 
              src={getAvatarUrl()} 
              alt="Profile" 
              className="profile-avatar"
              data-testid="profile-avatar"
            />
          </div>
        </header>
        
        {/* Main Content Area - Greeting */}
        <main className="main-content" data-testid="main-content">
          <div className="greeting-row" data-testid="greeting-row">
            <h1 className="greeting-text" data-testid="greeting-text">
              {greetingData.text}, {telegramUser?.first_name || 'Гость'}!
            </h1>
            <img 
              src={greetingData.icon} 
              alt="" 
              className="greeting-icon"
              data-testid="greeting-icon"
            />
          </div>
          
          {/* Training Streak */}
          <div className="streak-row" data-testid="streak-row">
            <img 
              src="/fire_strike.svg" 
              alt="" 
              className="streak-icon"
              data-testid="streak-icon"
            />
            <span className="streak-text" data-testid="streak-text">
              Тренировочная серия в течение 0 дней
            </span>
          </div>
          
          {/* Date Selector */}
          <DateSelector />
        </main>
      </div>
    </div>
  );
};

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Home />} />
        </Routes>
      </BrowserRouter>
    </div>
  );
}

export default App;
