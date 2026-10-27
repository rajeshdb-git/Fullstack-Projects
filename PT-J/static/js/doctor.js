document.addEventListener('DOMContentLoaded', () => {

    /* =========================================
       AI TREATMENT DESCRIPTION
       ========================================= */

    document.querySelectorAll('.doctor-generate-description').forEach((button) => {

        button.addEventListener('click', async () => {

            const form = button.closest('form');

            const nameField =
                form?.elements.namedItem('name');

            const descriptionField =
                form?.elements.namedItem('description');

            const csrfField =
                form?.querySelector('[name="csrfmiddlewaretoken"]');

            const status =
                form?.querySelector('.doctor-ai-status');

            const treatmentName =
                nameField?.value.trim();


            if (!treatmentName) {

                if (status) {
                    status.textContent =
                        'Enter a treatment name first.';

                    status.classList.add('is-error');
                }

                nameField?.focus();

                return;
            }


            if (
                !csrfField ||
                !descriptionField ||
                !status
            ) {
                return;
            }


            button.disabled = true;

            button.setAttribute(
                'aria-busy',
                'true'
            );

            status.classList.remove(
                'is-error'
            );

            status.textContent =
                'Generating a draft...';


            try {

                const formData =
                    new FormData(form);

                formData.set(
                    'name',
                    treatmentName
                );


                const response =
                    await fetch(
                        button.dataset.endpoint,
                        {
                            method: 'POST',

                            credentials:
                                'same-origin',

                            headers: {
                                'X-CSRFToken':
                                    csrfField.value,
                            },

                            body: formData,
                        }
                    );


                let result;


                try {

                    result =
                        await response.json();

                } catch {

                    throw new Error(
                        'The server returned an unexpected response. Please try again.'
                    );

                }


                if (!response.ok) {

                    throw new Error(
                        result.error ||
                        'Could not generate a draft.'
                    );

                }


                if (!result.description) {

                    throw new Error(
                        'The AI service returned an empty description.'
                    );

                }


                descriptionField.value =
                    result.description;


                descriptionField.dispatchEvent(
                    new Event(
                        'input',
                        {
                            bubbles: true
                        }
                    )
                );


                status.classList.remove(
                    'is-error'
                );


                status.textContent =
                    'Draft added. Review and edit it before saving.';


            } catch (error) {

                status.textContent =
                    error.message ||
                    'Could not generate a draft. Enter the description manually.';

                status.classList.add(
                    'is-error'
                );


            } finally {

                button.disabled = false;

                button.removeAttribute(
                    'aria-busy'
                );

            }

        });

    });


    /* =========================================
       UPDATE DOCTOR DETAILS MODAL
       ========================================= */

    const updateDoctorBtn =
        document.getElementById(
            'updateDoctorBtn'
        );


    const doctorDetailsModal =
        document.getElementById(
            'doctorDetailsModal'
        );


    const closeDoctorModal =
        document.getElementById(
            'closeDoctorModal'
        );


    const cancelDoctorModal =
        document.getElementById(
            'cancelDoctorModal'
        );


    const doctorModalOverlay =
        document.getElementById(
            'doctorModalOverlay'
        );


    if (
        !updateDoctorBtn ||
        !doctorDetailsModal
    ) {
        return;
    }


    function openDoctorModal() {

        doctorDetailsModal.classList.add(
            'active'
        );


        doctorDetailsModal.setAttribute(
            'aria-hidden',
            'false'
        );


        document.body.style.overflow =
            'hidden';
    }


    function closeDoctorModalFunction() {

        doctorDetailsModal.classList.remove(
            'active'
        );


        doctorDetailsModal.setAttribute(
            'aria-hidden',
            'true'
        );


        document.body.style.overflow =
            '';
    }


    updateDoctorBtn.addEventListener(
        'click',
        openDoctorModal
    );


    if (closeDoctorModal) {

        closeDoctorModal.addEventListener(
            'click',
            closeDoctorModalFunction
        );

    }


    if (cancelDoctorModal) {

        cancelDoctorModal.addEventListener(
            'click',
            closeDoctorModalFunction
        );

    }


    if (doctorModalOverlay) {

        doctorModalOverlay.addEventListener(
            'click',
            closeDoctorModalFunction
        );

    }


    document.addEventListener(
        'keydown',
        (event) => {

            if (
                event.key === 'Escape' &&
                doctorDetailsModal.classList.contains(
                    'active'
                )
            ) {

                closeDoctorModalFunction();

            }

        }
    );

});