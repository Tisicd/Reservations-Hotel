const CUSTOMER_KEY = 'reservas-uce-customer';
const TOKEN_KEY = 'reservas-uce-token';

function readCustomer() {
  try {
    return JSON.parse(sessionStorage.getItem(CUSTOMER_KEY) || 'null');
  } catch (_) {
    return null;
  }
}

export const state = {
  customer: readCustomer(),
  token: sessionStorage.getItem(TOKEN_KEY) || null,
  lastBooking: null,
  currentReservationId: null,
  currentEvents: [],
  currentNotifications: [],
  hotels: [],
  hotelDetails: new Map(),
  availability: new Map(),
};

export function getToken() {
  return state.token;
}

export function setSession(token, customer) {
  state.token = token;
  state.customer = customer;
  try {
    sessionStorage.setItem(TOKEN_KEY, token);
    sessionStorage.setItem(CUSTOMER_KEY, JSON.stringify(customer));
  } catch (_) {
    /* sessionStorage puede no estar disponible; la sesión sigue en memoria */
  }
}

export function clearSession() {
  state.token = null;
  state.customer = null;
  try {
    sessionStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(CUSTOMER_KEY);
  } catch (_) {
    /* ignorar */
  }
}
