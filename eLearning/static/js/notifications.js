// ====== Global AJAX Notifications & Messages ======

(function() {
  'use strict';

  // Configuration
  const config = {
    successDuration: 5000,  // 5 seconds
    errorDuration: 5000,
    messageFadeOutTime: 4500  // Start fading 500ms before removal
  };

  // Auto-dismiss Django messages with animation
  function initAutoMessagDismiss() {
    const alerts = document.querySelectorAll('.alert');

    alerts.forEach(alert => {
      // Skip if has 'alert-dismissible' with manual close
      if (alert.classList.contains('alert-dismissible')) {
        return;
      }

      const isSuccess = alert.classList.contains('alert-success') || alert.classList.contains('alert-info');
      const duration = isSuccess ? config.successDuration : config.errorDuration;

      // Set timeout to fade and remove
      setTimeout(() => {
        alert.style.transition = 'opacity 0.5s ease-out';
        alert.style.opacity = '0';

        setTimeout(() => {
          alert.remove();
        }, 500);
      }, duration);
    });
  }

  // Show a toast/notification
  window.showNotification = function(message, type = 'success') {
    const alertClass = type === 'success' ? 'alert-success' : 'alert-danger';
    const html = `
      <div class="alert ${alertClass} alert-dismissible fade show rounded-lg shadow-sm mb-3">
        <strong>${type === 'success' ? 'Succès' : 'Erreur'} :</strong> ${message}
        <button type="button" class="close" data-dismiss="alert"><span>&times;</span></button>
      </div>
    `;

    // Find alerts container or create one
    let container = document.querySelector('.alerts-container');
    if (!container) {
      container = document.createElement('div');
      container.className = 'alerts-container';
      document.body.insertBefore(container, document.body.firstChild);
    }

    // Insert notification
    const notification = document.createElement('div');
    notification.innerHTML = html;
    container.insertBefore(notification.firstChild, container.firstChild);

    // Auto-dismiss
    const alert = container.querySelector('.alert');
    setTimeout(() => {
      alert.style.opacity = '0';
      setTimeout(() => alert.remove(), 500);
    }, config.successDuration);
  };

  // AJAX Form Submission
  window.submitFormAjax = function(formId, endpoint, options = {}) {
    const form = document.getElementById(formId);
    if (!form) return console.error(`Form #${formId} not found`);

    form.addEventListener('submit', function(e) {
      e.preventDefault();

      const formData = new FormData(form);
      const method = form.getAttribute('method') || 'POST';

      fetch(endpoint, {
        method: method,
        body: formData,
        headers: {
          'X-Requested-With': 'XMLHttpRequest'
        }
      })
      .then(response => response.json())
      .then(data => {
        if (data.success) {
          showNotification(data.message || 'Opération réussie!', 'success');
          if (options.onSuccess) options.onSuccess(data);
          if (options.redirectTo) {
            setTimeout(() => window.location.href = options.redirectTo, 1500);
          }
          if (options.resetForm) form.reset();
        } else {
          showNotification(data.message || 'Une erreur s\'est produite', 'error');
          if (options.onError) options.onError(data);
        }
      })
      .catch(error => {
        console.error('Error:', error);
        showNotification('Erreur réseau. Veuillez réessayer.', 'error');
      });
    });
  };

  // Refresh page section with AJAX
  window.refreshSection = function(sectionId, endpoint, interval = 30000) {
    const section = document.getElementById(sectionId);
    if (!section) return console.error(`Section #${sectionId} not found`);

    function doRefresh() {
      fetch(endpoint, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
      })
      .then(response => response.text())
      .then(html => {
        section.innerHTML = html;
      })
      .catch(error => console.error('Refresh error:', error));
    }

    // Initial refresh
    doRefresh();

    // Repeat at interval
    return setInterval(doRefresh, interval);
  };

  // Page visibility monitoring (pause on tab blur, resume on focus)
  document.addEventListener('visibilitychange', function() {
    if (document.hidden) {
      // Page is hidden
      window.pageHidden = true;
    } else {
      // Page is visible
      window.pageHidden = false;
    }
  });

  // Initialize on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAutoMessagDismiss);
  } else {
    initAutoMessagDismiss();
  }

})();
