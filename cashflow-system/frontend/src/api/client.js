import axios from "axios";

/**
 * API manzili.
 *
 * Sukut bo'yicha — BO'SH satr, ya'ni so'rovlar sahifa ochilgan manzilning
 * o'ziga ketadi (/api/...). Nginx ularni backend'ga uzatadi.
 *
 * Nima uchun shunday:
 *   • Sayt qaysi manzildan ochilsa (localhost, 172.20.10.9, tunnel domeni,
 *     haqiqiy domen) — API o'sha manzilda bo'ladi. Hech narsa sozlanmaydi.
 *   • CORS muammosi umuman yo'q — manzil bir xil.
 *   • Faqat bitta port ochish kerak.
 *
 * VITE_API_URL faqat backend BOSHQA serverda turgan holat uchun.
 */
const API_BASE = import.meta.env.VITE_API_URL || "";

const client = axios.create({ baseURL: API_BASE });

client.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  // Backend xato xabarlarini shu til bo'yicha qaytaradi.
  // localStorage'dan o'qiladi, chunki bu React konteksti tashqarisidagi modul.
  const lang = localStorage.getItem("lang");
  if (lang) {
    config.headers["Accept-Language"] = lang;
  }
  return config;
});

client.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem("token");
      window.location.href = "/login";
    }
    return Promise.reject(err);
  }
);

export default client;
