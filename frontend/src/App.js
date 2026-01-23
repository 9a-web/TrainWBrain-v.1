import { useEffect, useState } from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const Home = () => {
  const [telegramUser, setTelegramUser] = useState(null);

  const helloWorldApi = async () => {
    try {
      const response = await axios.get(`${API}/`);
      console.log(response.data.message);
    } catch (e) {
      console.error(e, `errored out requesting / api`);
    }
  };

  useEffect(() => {
    helloWorldApi();
    
    // Get Telegram WebApp user data
    if (window.Telegram?.WebApp) {
      const tg = window.Telegram.WebApp;
      tg.ready();
      tg.expand();
      
      if (tg.initDataUnsafe?.user) {
        setTelegramUser(tg.initDataUnsafe.user);
      }
    }
  }, []);

  // Get user avatar URL from Telegram
  const getAvatarUrl = () => {
    if (telegramUser?.photo_url) {
      return telegramUser.photo_url;
    }
    // Default avatar placeholder
    return `https://ui-avatars.com/api/?name=${telegramUser?.first_name || 'U'}&background=FF6B00&color=fff&size=80`;
  };

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
              <Menu size={24} strokeWidth={2} />
            </button>
            
            <img 
              src={getAvatarUrl()} 
              alt="Profile" 
              className="profile-avatar"
              data-testid="profile-avatar"
            />
          </div>
        </header>
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
