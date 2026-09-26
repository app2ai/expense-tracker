// main.js — students will add JavaScript here as features are built

// Analytics coming-soon page: swap the notify button for its confirmation.
document.querySelectorAll("[data-notify-button]").forEach((button) => {
    button.addEventListener("click", () => {
        button.hidden = true;
        button.nextElementSibling.hidden = false;
    });
});
