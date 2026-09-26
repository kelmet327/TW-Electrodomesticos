document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("pos-form");
    const dataElement = document.getElementById("pos-data");
    if (!form || !dataElement) return;

    const jsonElement = document.getElementById("pos-products-json");
    let products = [];
    try {
        products = JSON.parse(jsonElement?.textContent || "[]");
    } catch (_error) {
        products = [];
    }

    const productMap = new Map(products.map((product) => [Number(product.id_producto), product]));
    const cart = new Map();
    const searchInput = document.getElementById("pos-search");
    const categoryInput = document.getElementById("pos-category");
    const cartItems = document.getElementById("cart-items");
    const cartEmpty = document.getElementById("cart-empty");
    const cartSubtotal = document.getElementById("cart-subtotal");
    const cartTax = document.getElementById("cart-tax");
    const cartTotal = document.getElementById("cart-total");
    const taxLabel = document.getElementById("tax-label");
    const checkoutButton = document.getElementById("checkout-submit");
    const clearButton = document.getElementById("clear-cart");
    const methodInput = document.getElementById("metodo");
    const referenceField = document.getElementById("reference-field");
    const noResults = document.getElementById("pos-no-results");
    const productCounter = document.getElementById("product-counter");
    const currency = new Intl.NumberFormat("es-BO", {
        style: "currency",
        currency: "BOB",
        minimumFractionDigits: 2,
    });

    const rawTaxRate = Number(dataElement.dataset.taxRate || 0);
    const taxRate = Number.isFinite(rawTaxRate) ? (rawTaxRate > 1 ? rawTaxRate / 100 : rawTaxRate) : 0;
    const toCents = (value) => Math.round(Number(value) * 100);
    const money = (cents) => `Bs. ${new Intl.NumberFormat("es-BO", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    }).format(cents / 100)}`;

    function announce(message) {
        let liveRegion = document.getElementById("pos-live-region");
        if (!liveRegion) {
            liveRegion = document.createElement("div");
            liveRegion.id = "pos-live-region";
            liveRegion.className = "sr-only";
            liveRegion.setAttribute("aria-live", "polite");
            document.body.appendChild(liveRegion);
        }
        liveRegion.textContent = message;
    }

    function addProduct(productId) {
        const product = productMap.get(Number(productId));
        if (!product) return;
        const current = cart.get(Number(productId))?.quantity || 0;
        if (current >= Number(product.stock)) {
            announce(`No hay más unidades disponibles de ${product.nombre}.`);
            return;
        }
        cart.set(Number(productId), { product, quantity: current + 1 });
        renderCart();
        announce(`${product.nombre} agregado al carrito.`);
    }

    function changeQuantity(productId, delta) {
        const entry = cart.get(Number(productId));
        if (!entry) return;
        const next = entry.quantity + delta;
        if (next <= 0) {
            cart.delete(Number(productId));
        } else if (next <= Number(entry.product.stock)) {
            entry.quantity = next;
        } else {
            announce("No existen más unidades de este producto.");
        }
        renderCart();
    }

    function createHiddenInput(name, value) {
        const input = document.createElement("input");
        input.type = "hidden";
        input.name = name;
        input.value = value;
        return input;
    }

    function renderCart() {
        cartItems.querySelectorAll(".cart-item, .cart-line-inputs").forEach((node) => node.remove());
        let subtotal = 0;

        cart.forEach((entry, productId) => {
            const lineTotal = toCents(entry.product.precio) * entry.quantity;
            subtotal += lineTotal;
            const item = document.createElement("div");
            item.className = "cart-item";

            const info = document.createElement("div");
            info.className = "cart-item-info";
            const name = document.createElement("strong");
            name.textContent = entry.product.nombre;
            const meta = document.createElement("small");
            meta.textContent = `${money(toCents(entry.product.precio))} c/u`;
            info.append(name, meta);

            const controls = document.createElement("div");
            controls.className = "quantity-control";
            const minus = document.createElement("button");
            minus.type = "button";
            minus.dataset.action = "minus";
            minus.dataset.id = productId;
            minus.setAttribute("aria-label", `Quitar una unidad de ${entry.product.nombre}`);
            minus.textContent = "−";
            const quantity = document.createElement("span");
            quantity.textContent = entry.quantity;
            const plus = document.createElement("button");
            plus.type = "button";
            plus.dataset.action = "plus";
            plus.dataset.id = productId;
            plus.setAttribute("aria-label", `Agregar una unidad de ${entry.product.nombre}`);
            plus.textContent = "+";
            controls.append(minus, quantity, plus);

            const total = document.createElement("strong");
            total.className = "cart-item-total";
            total.textContent = money(lineTotal);

            const lineInputs = document.createElement("div");
            lineInputs.className = "cart-line-inputs";
            lineInputs.append(createHiddenInput("producto_id", productId), createHiddenInput("cantidad", entry.quantity));
            item.append(info, controls, total, lineInputs);
            cartItems.appendChild(item);
        });

        const tax = Math.round(subtotal * taxRate);
        const total = subtotal + tax;
        cartEmpty.hidden = cart.size > 0;
        cartSubtotal.textContent = money(subtotal);
        cartTax.textContent = money(tax);
        cartTotal.textContent = money(total);
        taxLabel.textContent = `(${(taxRate * 100).toLocaleString("es-BO", { maximumFractionDigits: 2 })})`;
        clearButton.hidden = cart.size === 0;
        checkoutButton.disabled = cart.size === 0;
        checkoutButton.dataset.total = total;
    }

    document.querySelectorAll(".add-product").forEach((button) => {
        button.addEventListener("click", () => addProduct(button.dataset.id));
    });

    cartItems.addEventListener("click", (event) => {
        const button = event.target.closest("button[data-action]");
        if (!button) return;
        changeQuantity(button.dataset.id, button.dataset.action === "plus" ? 1 : -1);
    });

    clearButton.addEventListener("click", () => {
        cart.clear();
        renderCart();
        announce("El carrito fue vacío.");
    });

    function filterProducts() {
        const query = searchInput.value.trim().toLocaleLowerCase("es");
        const category = categoryInput.value;
        let visible = 0;
        document.querySelectorAll(".pos-product").forEach((card) => {
            const matchesText = !query || card.dataset.name.includes(query);
            const matchesCategory = !category || card.dataset.category === category;
            const show = matchesText && matchesCategory;
            card.hidden = !show;
            if (show) visible += 1;
        });
        productCounter.textContent = visible;
        noResults.hidden = visible !== 0;
    }

    searchInput.addEventListener("input", filterProducts);
    categoryInput.addEventListener("change", filterProducts);

    function updateReferenceVisibility() {
        const requiresReference = methodInput.value && methodInput.value !== "efectivo";
        referenceField.hidden = !requiresReference;
        referenceField.querySelector("input").required = false;
    }
    methodInput.addEventListener("change", updateReferenceVisibility);
    updateReferenceVisibility();

    form.addEventListener("submit", (event) => {
        if (cart.size === 0 || !methodInput.value) {
            event.preventDefault();
            announce(cart.size === 0 ? "Agrega productos al carrito." : "Selecciona un método de pago.");
            return;
        }
        checkoutButton.disabled = true;
        checkoutButton.textContent = "Registrando venta…";
    });

    renderCart();
    filterProducts();
});
