"use strict";

const grid = document.querySelector("#product-grid");
const search = document.querySelector("#search");
const filters = document.querySelector("#filters-form");
const count = document.querySelector("#result-count");
const message = document.querySelector("#message");
const empty = document.querySelector("#empty-state");
const dialog = document.querySelector("#product-dialog");
const fallbackImage = "/static/perfume.svg";
const money = new Intl.NumberFormat("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 0 });
const swatches = ["#e8e8dc", "#e9dfd4", "#e0e5da", "#e9e3dc", "#dfdfd5", "#e4e7dd"];
let products = [];
let allProducts = null;
let controller;
let requestId = 0;
let debounce;
const initialControls = [search, ...filters.querySelectorAll("input, select")];
initialControls.forEach(control => { control.disabled = true; });

if (matchMedia("(max-width: 760px)").matches) document.querySelector("#filter-panel").open = false;

function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

function imageSource(product) {
  if (!product.image_url) return fallbackImage;
  try {
    const url = new URL(product.image_url, location.origin);
    return ["http:", "https:"].includes(url.protocol) ? url.href : fallbackImage;
  } catch {
    return fallbackImage;
  }
}

function setProductImage(img, product) {
  img.onerror = () => {
    img.onerror = null;
    img.src = fallbackImage;
  };
  img.src = imageSource(product);
  img.alt = `Perfume ${product.name}`;
}

function colorFor(product) {
  let value = 0;
  for (const letter of product.id) value += letter.charCodeAt(0);
  return swatches[value % swatches.length];
}

function populateFilters(catalog) {
  for (const field of ["brand", "gender", "family", "presentation_ml"]) {
    const select = filters.elements.namedItem(field);
    const values = [...new Set(catalog.map(product => product[field]))];
    values.sort((a, b) => field === "presentation_ml" ? a - b : String(a).localeCompare(String(b), "es"));
    for (const value of values) {
      const option = node("option", "", field === "presentation_ml" ? `${value} ml` : value);
      option.value = value;
      select.append(option);
    }
  }
}

function openProduct(product) {
  document.querySelector("#detail-name").textContent = product.name;
  document.querySelector("#detail-brand").textContent = product.brand;
  document.querySelector("#detail-description").textContent = product.description || "Descripción por completar.";
  document.querySelector("#detail-price").textContent = money.format(product.price);
  setProductImage(document.querySelector("#detail-image"), product);
  document.querySelector("#detail-art").style.setProperty("--swatch", colorFor(product));
  const attributes = document.querySelector("#detail-attributes");
  attributes.replaceChildren();
  for (const [label, value] of [["Género", product.gender], ["Familia olfativa", product.family], ["Presentación", `${product.presentation_ml} ml`], ["Disponibilidad", product.stock > 0 ? `${product.stock} unidades disponibles` : "Agotado"]]) {
    const row = node("div");
    row.append(node("dt", "", label), node("dd", "", value));
    attributes.append(row);
  }
  dialog.showModal();
}

function render(catalog) {
  grid.replaceChildren();
  for (const product of catalog) {
    const card = node("article", "product-card");
    const button = node("button", "product-open");
    button.type = "button";
    button.setAttribute("aria-label", `Ver detalles de ${product.name}`);
    const art = node("div", "product-image");
    art.style.setProperty("--swatch", colorFor(product));
    const img = node("img");
    img.loading = "lazy";
    img.decoding = "async";
    setProductImage(img, product);
    art.append(img);
    if (product.stock === 0) art.append(node("span", "stock-tag", "Agotado"));
    const info = node("div", "product-info");
    const title = node("div", "product-title-row");
    const arrow = node("span", "", "↗");
    arrow.setAttribute("aria-hidden", "true");
    title.append(node("h3", "", product.name), arrow);
    const bottom = node("div", "product-bottom");
    bottom.append(node("span", "product-price", money.format(product.price)), node("span", "product-volume", `${product.presentation_ml} ml`));
    info.append(node("p", "product-meta", product.brand), title, node("p", "product-family", `${product.family} · ${product.gender}`), bottom);
    button.append(art, info);
    button.addEventListener("click", () => openProduct(product));
    card.append(button);
    grid.append(card);
  }
  empty.hidden = catalog.length !== 0;
  count.textContent = `${catalog.length} ${catalog.length === 1 ? "perfume" : "perfumes"}`;
}

function showMessage(text, retry = false) {
  message.replaceChildren(node("span", "", text));
  if (retry) {
    const button = node("button", "", "Volver a intentar");
    button.type = "button";
    button.addEventListener("click", loadProducts);
    message.append(button);
  }
  message.hidden = false;
}

function getParams() {
  const params = new URLSearchParams();
  if (search.value.trim()) params.set("q", search.value.trim());
  for (const key of ["brand", "gender", "family", "presentation_ml", "min_price", "max_price"]) {
    const input = filters.elements.namedItem(key);
    if (!input.validity.valid) throw new Error("Revisa los precios: deben ser números iguales o mayores que cero.");
    if (input.value) params.set(key, input.value);
  }
  const min = filters.elements.namedItem("min_price").value;
  const max = filters.elements.namedItem("max_price").value;
  if (min !== "" && max !== "" && Number(min) > Number(max)) throw new Error("El precio desde no puede ser mayor que el precio hasta.");
  if (filters.elements.namedItem("in_stock").checked) params.set("in_stock", "true");
  return params;
}

async function loadProducts() {
  clearTimeout(debounce);
  controller?.abort();
  const current = ++requestId;
  message.hidden = true;
  let params;
  try {
    params = getParams();
  } catch (error) {
    grid.replaceChildren();
    grid.setAttribute("aria-busy", "false");
    empty.hidden = true;
    count.textContent = "Revisa los filtros";
    showMessage(error.message);
    return;
  }
  controller = new AbortController();
  grid.setAttribute("aria-busy", "true");
  count.textContent = "Buscando perfumes…";
  try {
    const response = await fetch(`/api/search/advanced?${params}`, { signal: controller.signal });
    if (!response.ok) throw new Error("No pudimos consultar el catálogo. Inténtalo de nuevo.");
    const catalog = await response.json();
    if (!Array.isArray(catalog)) throw new Error("No pudimos leer los perfumes. Inténtalo de nuevo.");
    if (current !== requestId) return;
    products = catalog;
    if (allProducts === null && params.size === 0) {
      allProducts = catalog;
      populateFilters(catalog);
      initialControls.forEach(control => { control.disabled = false; });
    }
    render(products);
  } catch (error) {
    if (error.name === "AbortError" || current !== requestId) return;
    grid.replaceChildren();
    empty.hidden = true;
    count.textContent = "Catálogo no disponible";
    showMessage(error.message, true);
  } finally {
    if (current === requestId) grid.setAttribute("aria-busy", "false");
  }
}

function reset() {
  filters.reset();
  search.value = "";
  loadProducts();
}

document.querySelector("#search-form").addEventListener("submit", event => { event.preventDefault(); loadProducts(); });
filters.addEventListener("submit", event => { event.preventDefault(); loadProducts(); });
filters.addEventListener("change", loadProducts);
filters.addEventListener("input", event => {
  if (event.target.type === "number") {
    clearTimeout(debounce);
    debounce = setTimeout(loadProducts, 250);
  }
});
search.addEventListener("input", () => { clearTimeout(debounce); debounce = setTimeout(loadProducts, 250); });
document.querySelector("#clear-filters").addEventListener("click", reset);
document.querySelector("#reset-search").addEventListener("click", reset);
document.querySelector("#close-detail").addEventListener("click", () => dialog.close());
dialog.addEventListener("click", event => {
  const rect = dialog.getBoundingClientRect();
  if (event.target === dialog && (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom)) dialog.close();
});
loadProducts();
