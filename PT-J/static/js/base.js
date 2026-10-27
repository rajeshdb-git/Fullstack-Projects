document.addEventListener("DOMContentLoaded", function () {
    const menuButton = document.getElementById("menu-button");
    const navigation = document.getElementById("header_ryt");
    const services = document.querySelector(".services");
    const appointmentOverlay = document.getElementById("appointment-overlay");
    const appointmentClose = document.getElementById("appointment-close");
    const appointmentButtons = document.querySelectorAll("#open-appointment, .open-appointment");
    const appointmentMessages = document.querySelectorAll(".appointment-message");

    function closeAppointment() {
        if (appointmentOverlay) {
            appointmentOverlay.classList.remove("active");
        }
        document.body.style.overflow = "";
    }

    if (menuButton && navigation) {
        menuButton.addEventListener("click", function () {
            navigation.classList.toggle("active");
            const icon = menuButton.querySelector("i");

            if (navigation.classList.contains("active")) {
                icon.classList.remove("fa-bars");
                icon.classList.add("fa-xmark");
            } else {
                icon.classList.remove("fa-xmark");
                icon.classList.add("fa-bars");
            }
        });
    }

    if (services) {
        const serviceLink = services.querySelector(".header-a");

        if (serviceLink) {
            serviceLink.addEventListener("click", function (event) {
                if (window.innerWidth <= 768) {
                    event.preventDefault();
                    services.classList.toggle("active");
                }
            });
        }
    }

    if (appointmentOverlay && (appointmentMessages.length > 0 || window.location.search.includes("success=1") || window.location.hash === "#appointment-overlay")) {
        appointmentOverlay.classList.add("active");
        document.body.style.overflow = "hidden";

        const successMessage = document.querySelector('.appointment-message.success');
        if (successMessage) {
            const appointmentForm = document.getElementById('appointment-form');
            if (appointmentForm) {
                appointmentForm.classList.add('appointment-form--hidden');
            }
        }
    }

    appointmentButtons.forEach(function (button) {
        button.addEventListener("click", function () {
            if (appointmentOverlay) {
                appointmentOverlay.classList.add("active");
                document.body.style.overflow = "hidden";
            }
        });
    });

    if (appointmentClose) {
        appointmentClose.addEventListener("click", closeAppointment);
    }

    if (appointmentOverlay) {
        appointmentOverlay.addEventListener("click", function (event) {
            if (event.target === appointmentOverlay) {
                closeAppointment();
            }
        });
    }

    document.querySelectorAll('.treatment-faq-item').forEach(function (item, index) {
        const button = item.querySelector('.treatment-faq-question');
        if (!button) return;

        const answerWrap = item.querySelector('.treatment-faq-answer-wrap');
        const updateState = function (shouldOpen) {
            item.classList.toggle('open', shouldOpen);
            button.setAttribute('aria-expanded', String(shouldOpen));
            if (answerWrap) {
                answerWrap.style.display = shouldOpen ? 'block' : 'none';
            }
        };

        if (index === 0) {
            updateState(true);
        } else {
            updateState(false);
        }

        button.addEventListener('click', function () {
            const isOpen = item.classList.contains('open');
            document.querySelectorAll('.treatment-faq-item').forEach(function (faqItem) {
                const faqButton = faqItem.querySelector('.treatment-faq-question');
                const faqWrap = faqItem.querySelector('.treatment-faq-answer-wrap');
                faqItem.classList.remove('open');
                if (faqButton) faqButton.setAttribute('aria-expanded', 'false');
                if (faqWrap) faqWrap.style.display = 'none';
            });

            if (!isOpen) {
                updateState(true);
            }
        });
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape" && appointmentOverlay && appointmentOverlay.classList.contains("active")) {
            closeAppointment();
        }
    });
});