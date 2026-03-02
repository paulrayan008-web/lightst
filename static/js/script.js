document.getElementById("uploadForm").addEventListener("submit", function(e) {

    let fileInput = document.getElementById("imageInput");

    if (fileInput.files.length > 0) {
        if (fileInput.files[0].size >50 * 1024 * 1024) {
            alert("Image too large! Max 2MB allowed.");
            e.preventDefault();
        }
    }
});