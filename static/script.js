// Simple JavaScript for the FastAPI CRUD Backend frontend
document.addEventListener('DOMContentLoaded', function() {
    console.log('FastAPI CRUD Backend - Static files loaded successfully!');
    
    // Add some interactive functionality
    const buttons = document.querySelectorAll('.btn');
    
    buttons.forEach(button => {
        button.addEventListener('click', function(e) {
            // Add a small animation effect
            this.style.transform = 'scale(0.95)';
            setTimeout(() => {
                this.style.transform = '';
            }, 150);
        });
    });
    
    // Display current time
    function updateTime() {
        const now = new Date();
        const timeString = now.toLocaleTimeString();
        
        // Create time display if it doesn't exist
        if (!document.getElementById('current-time')) {
            const timeDiv = document.createElement('div');
            timeDiv.id = 'current-time';
            timeDiv.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                background: rgba(102, 126, 234, 0.9);
                color: white;
                padding: 10px 15px;
                border-radius: 20px;
                font-size: 14px;
                font-weight: 600;
                box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
            `;
            document.body.appendChild(timeDiv);
        }
        
        document.getElementById('current-time').textContent = `Current Time: ${timeString}`;
    }
    
    // Update time every second
    updateTime();
    setInterval(updateTime, 1000);
});
