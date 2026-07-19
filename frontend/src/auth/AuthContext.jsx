import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import { apiRequest } from "../api";

const TOKEN_KEY = "webscope_access_token";
const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => window.localStorage.getItem(TOKEN_KEY));
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;

    async function restoreSession() {
      const savedToken = window.localStorage.getItem(TOKEN_KEY);
      if (!savedToken) {
        if (active) setLoading(false);
        return;
      }

      try {
        const currentUser = await fetchCurrentUser(savedToken);
        if (!active) return;
        setToken(savedToken);
        setUser(currentUser);
      } catch {
        window.localStorage.removeItem(TOKEN_KEY);
        if (!active) return;
        setToken(null);
        setUser(null);
      } finally {
        if (active) setLoading(false);
      }
    }

    restoreSession();
    return () => {
      active = false;
    };
  }, []);

  async function login({ email, password }) {
    const result = await apiRequest("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    window.localStorage.setItem(TOKEN_KEY, result.access_token);
    setToken(result.access_token);
    const currentUser = await fetchCurrentUser(result.access_token);
    setUser(currentUser);
    return currentUser;
  }

  async function register({ name, email, password }) {
    await apiRequest("/auth/register", {
      method: "POST",
      body: JSON.stringify({ name, email, password }),
    });
    return login({ email, password });
  }

  function logout() {
    window.localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setUser(null);
  }

  const value = useMemo(
    () => ({
      user,
      token,
      loading,
      isAuthenticated: Boolean(user && token),
      login,
      register,
      logout,
    }),
    [user, token, loading],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}

async function fetchCurrentUser(accessToken) {
  return apiRequest("/auth/me", {
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  });
}
