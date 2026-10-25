const STORAGE_KEY = 'reservas-uce-customer';

function readCustomer() {
  try {
    return JSON.parse(sessionStorage.getItem(STORAGE_KEY) || 'null');
  } catch (_) {
    return null;
  }
}

export const state = {
  customer: readCustomer(),
  lastBooking: null,
  currentReservationId: null,
  currentEvents: [],
  currentNotifications: [],
  hotels: [],
  hotelDetails: new Map(),
  availability: new Map(),
};

export function setCustomer(customer) {
  state.customer = customer;
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(customer));
  } catch (_) {
    /* sessionStorage puede no estar disponible; la sesión sigue en memoria */
  }
}

export function clearCustomer() {
  state.customer = null;
  try {
    sessionStorage.removeItem(STORAGE_KEY);
  } catch (_) {
    /* ignorar */
  }
}
