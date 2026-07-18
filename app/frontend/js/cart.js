// cart.js — simple client-side cart. Real backend order is only created when the
// customer proceeds to checkout (POST /orders) — the cart itself doesn't need a
// backend table since it's just "what the customer is currently considering."

const CART_KEY = "vs_cart";

function getCart() {
  const raw = sessionStorage.getItem(CART_KEY);
  return raw ? JSON.parse(raw) : [];
}

function saveCart(items) {
  sessionStorage.setItem(CART_KEY, JSON.stringify(items));
}

function addToCart(product) {
  // product: { product_id, product_name, store_id, store_name, selling_price, quantity_available }
  const cart = getCart();
  const existing = cart.find(i => i.product_id === product.product_id);
  if (existing) {
    existing.quantity = Math.min(existing.quantity + 1, product.quantity_available);
  } else {
    cart.push({ ...product, quantity: 1 });
  }
  saveCart(cart);
}

function updateCartQuantity(productId, delta) {
  const cart = getCart();
  const item = cart.find(i => i.product_id === productId);
  if (!item) return;
  item.quantity = Math.max(1, Math.min(item.quantity + delta, item.quantity_available));
  saveCart(cart);
}

function removeFromCart(productId) {
  saveCart(getCart().filter(i => i.product_id !== productId));
}

function clearCart() {
  sessionStorage.removeItem(CART_KEY);
}

function cartTotal() {
  return getCart().reduce((sum, i) => sum + i.selling_price * i.quantity, 0);
}

function cartCount() {
  return getCart().reduce((sum, i) => sum + i.quantity, 0);
}