document.addEventListener("DOMContentLoaded", function () {
    const deleteButtons = document.querySelectorAll(".confirm-delete");

    deleteButtons.forEach(function (button) {
        button.addEventListener("click", function (event) {
            const ok = window.confirm("Are you sure you want to delete this item?");
            if (!ok) {
                event.preventDefault();
            }
        });
    });
});
