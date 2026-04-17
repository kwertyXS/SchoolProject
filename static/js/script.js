document.getElementById('showRegister').addEventListener('click', function (e) {
    e.preventDefault();
    document.querySelector('.sign-in-container').style.display = 'none';
    document.querySelector('.sign-up-container').style.display = 'flex';
});

document.getElementById('showLogin').addEventListener('click', function (e) {
    e.preventDefault();
    document.querySelector('.sign-up-container').style.display = 'none';
    document.querySelector('.sign-in-container').style.display = 'flex';
});

// Начальный estado
document.querySelector('.sign-up-container').style.display = 'none';
