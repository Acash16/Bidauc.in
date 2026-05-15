function toggleProfileForm() {
    let viewMode = document.getElementById('profile-view-mode');
    let editMode = document.getElementById('profile-edit-mode');
    
    if (viewMode && viewMode.style.display !== 'none') {
        viewMode.style.display = 'none';
        editMode.style.display = 'block';
    } else if (viewMode) {
        viewMode.style.display = 'flex';
        editMode.style.display = 'none';
    }
    editMode.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

document.addEventListener("DOMContentLoaded", function() {
    const pinInput = document.getElementById("pincode");
    if (pinInput) {
        pinInput.addEventListener("blur", function() {
            let pin = this.value.trim();
            if (pin.length === 6) {
                fetch("/get_location/" + pin)
                .then(res => res.json())
                .then(data => {
                    if(data.state){
                        document.getElementById("state").value = data.state;
                        document.getElementById("city").value = data.city;
                    }
                });
            }
        });
    }
});