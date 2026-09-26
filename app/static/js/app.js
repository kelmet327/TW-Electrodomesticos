document.addEventListener("DOMContentLoaded", () => {
    const body = document.body;
    const sidebar = document.getElementById("sidebar");
    const sidebarToggles = document.querySelectorAll("[data-sidebar-toggle]");
    const publicToggle = document.querySelector("[data-public-toggle]");
    const publicNav = document.getElementById("public-nav");

    sidebarToggles.forEach((toggle) => {
        toggle.addEventListener("click", () => {
            const isOpen = body.classList.toggle("sidebar-open");
            toggle.setAttribute("aria-expanded", String(isOpen));
        });
    });

    if (publicToggle && publicNav) {
        publicToggle.addEventListener("click", () => {
            const isOpen = body.classList.toggle("public-nav-open");
            publicToggle.setAttribute("aria-expanded", String(isOpen));
        });
    }

    document.querySelectorAll("[data-dismiss-flash]").forEach((button) => {
        button.addEventListener("click", () => button.closest(".flash")?.remove());
    });
    document.querySelectorAll(".flash-success").forEach((flash) => {
        window.setTimeout(() => {
            flash.classList.add("flash-hide");
            window.setTimeout(() => flash.remove(), 250);
        }, 6000);
    });

    document.querySelectorAll("[data-toggle-password]").forEach((button) => {
        button.addEventListener("click", () => {
            const input = button.parentElement?.querySelector("input");
            if (!input) return;
            const show = input.type === "password";
            input.type = show ? "text" : "password";
            button.textContent = show ? "Ocultar" : "Ver";
            button.setAttribute("aria-label", show ? "Ocultar contraseña" : "Mostrar contraseña");
        });
    });

    document.querySelectorAll("form[data-confirm]").forEach((form) => {
        form.addEventListener("submit", (event) => {
            if (!window.confirm(form.dataset.confirm || "¿Confirmar esta acción?")) {
                event.preventDefault();
            }
        });
    });

    document.querySelectorAll("img").forEach((image) => {
        image.addEventListener("error", () => {
            const fallback = "/static/img/product-placeholder.svg";
            if (!image.src.endsWith(fallback)) image.src = fallback;
        });
    });

    document.addEventListener("click", (event) => {
        document.querySelectorAll("details.user-menu[open]").forEach((menu) => {
            if (!menu.contains(event.target)) menu.removeAttribute("open");
        });
    });
});
