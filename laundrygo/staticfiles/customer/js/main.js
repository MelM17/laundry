// Main JavaScript file for LaundryGo customer interface

document.addEventListener('DOMContentLoaded', function() {
    // Initialize components
    initializeRatingStars();
    initializeFormValidation();
    
    // Close alert messages after 5 seconds
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(function(alert) {
        setTimeout(function() {
            alert.style.opacity = '0';
            setTimeout(function() {
                alert.style.display = 'none';
            }, 500);
        }, 5000);
    });
});

// Initialize star rating functionality
function initializeRatingStars() {
    const starLabels = document.querySelectorAll('.star-rating label');
    if (starLabels.length > 0) {
        starLabels.forEach(function(label) {
            label.addEventListener('mouseover', function() {
                // Reset all stars
                starLabels.forEach(function(l) {
                    l.classList.remove('hovered');
                });
                
                // Highlight current star and all stars before it
                let currentLabel = this;
                while (currentLabel) {
                    currentLabel.classList.add('hovered');
                    currentLabel = currentLabel.previousElementSibling;
                    if (currentLabel && currentLabel.tagName !== 'LABEL') {
                        currentLabel = currentLabel.previousElementSibling;
                    }
                }
            });
            
            label.addEventListener('mouseout', function() {
                // Remove hover effect
                starLabels.forEach(function(l) {
                    l.classList.remove('hovered');
                });
            });
        });
    }
}

// Form validation
function initializeFormValidation() {
    const forms = document.querySelectorAll('form');
    forms.forEach(function(form) {
        form.addEventListener('submit', function(event) {
            let isValid = true;
            
            // Validate required fields
            const requiredFields = form.querySelectorAll('[required]');
            requiredFields.forEach(function(field) {
                if (!field.value.trim()) {
                    isValid = false;
                    field.classList.add('is-invalid');
                    
                    // Create error message if it doesn't exist
                    let errorMsg = field.nextElementSibling;
                    if (!errorMsg || !errorMsg.classList.contains('error-message')) {
                        errorMsg = document.createElement('div');
                        errorMsg.classList.add('error-message');
                        errorMsg.style.color = '#dc3545';
                        errorMsg.style.fontSize = '0.875rem';
                        errorMsg.style.marginTop = '5px';
                        field.parentNode.insertBefore(errorMsg, field.nextSibling);
                    }
                    errorMsg.textContent = 'This field is required';
                } else {
                    field.classList.remove('is-invalid');
                    
                    // Remove error message if it exists
                    const errorMsg = field.nextElementSibling;
                    if (errorMsg && errorMsg.classList.contains('error-message')) {
                        errorMsg.remove();
                    }
                }
            });
            
            // Validate email fields
            const emailFields = form.querySelectorAll('input[type="email"]');
            emailFields.forEach(function(field) {
                if (field.value.trim() && !isValidEmail(field.value)) {
                    isValid = false;
                    field.classList.add('is-invalid');
                    
                    // Create error message if it doesn't exist
                    let errorMsg = field.nextElementSibling;
                    if (!errorMsg || !errorMsg.classList.contains('error-message')) {
                        errorMsg = document.createElement('div');
                        errorMsg.classList.add('error-message');
                        errorMsg.style.color = '#dc3545';
                        errorMsg.style.fontSize = '0.875rem';
                        errorMsg.style.marginTop = '5px';
                        field.parentNode.insertBefore(errorMsg, field.nextSibling);
                    }
                    errorMsg.textContent = 'Please enter a valid email address';
                }
            });
            
            // Validate password fields
            const passwordField = form.querySelector('input[name="password1"]');
            const confirmPasswordField = form.querySelector('input[name="password2"]');
            if (passwordField && confirmPasswordField) {
                if (passwordField.value !== confirmPasswordField.value) {
                    isValid = false;
                    confirmPasswordField.classList.add('is-invalid');
                    
                    // Create error message if it doesn't exist
                    let errorMsg = confirmPasswordField.nextElementSibling;
                    if (!errorMsg || !errorMsg.classList.contains('error-message')) {
                        errorMsg = document.createElement('div');
                        errorMsg.classList.add('error-message');
                        errorMsg.style.color = '#dc3545';
                        errorMsg.style.fontSize = '0.875rem';
                        errorMsg.style.marginTop = '5px';
                        confirmPasswordField.parentNode.insertBefore(errorMsg, confirmPasswordField.nextSibling);
                    }
                    errorMsg.textContent = 'Passwords do not match';
                }
            }
            
            if (!isValid) {
                event.preventDefault();
            }
        });
    });
}

// Email validation helper
function isValidEmail(email) {
    const re = /^(([^<>()\[\]\\.,;:\s@"]+(\.[^<>()\[\]\\.,;:\s@"]+)*)|(".+"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/;
    return re.test(String(email).toLowerCase());
}