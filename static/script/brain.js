console.log("script.js loaded");

document.addEventListener('DOMContentLoaded', function () {
  console.log("DOM ready");

  const slides = document.querySelectorAll('.slide');
  const dots   = document.querySelectorAll('.dot');
  const leftBtn  = document.querySelector('.left-btn');
  const rightBtn = document.querySelector('.right-btn');
  const heroSlider = document.querySelector('.hero-slider');

  console.log("slides found:", slides.length);
  console.log("dots found:", dots.length);
  console.log("leftBtn:", leftBtn);
  console.log("rightBtn:", rightBtn);
  console.log("heroSlider:", heroSlider);

  if (slides.length === 0) {
    console.error("NO SLIDES FOUND - check your HTML class names");
    return;
  }

  if (!leftBtn || !rightBtn) {
    console.error("BUTTONS NOT FOUND - check your HTML class names");
    return;
  }

  let currentSlide = 0;
  let autoSlideInterval;

  function goToSlide(index) {
    console.log("going to slide", index);
    slides[currentSlide].classList.remove('active');
    slides[currentSlide].classList.add('exit-left');
    if (dots[currentSlide]) dots[currentSlide].classList.remove('active');

    const exiting = slides[currentSlide];
    setTimeout(() => exiting.classList.remove('exit-left'), 500);

    currentSlide = (index + slides.length) % slides.length;
    slides[currentSlide].classList.add('active');
    if (dots[currentSlide]) dots[currentSlide].classList.add('active');
  }

  function changeSlide(direction) {
    console.log("changeSlide called, direction:", direction);
    goToSlide(currentSlide + direction);
    resetAutoSlide();
  }

  function resetAutoSlide() {
    clearInterval(autoSlideInterval);
    autoSlideInterval = setInterval(() => changeSlide(1), 4000);
  }

  leftBtn.addEventListener('click', function () {
    console.log("LEFT clicked");
    changeSlide(-1);
  });

  rightBtn.addEventListener('click', function () {
    console.log("RIGHT clicked");
    changeSlide(1);
  });

  dots.forEach((dot, i) => {
    dot.addEventListener('click', () => {
      goToSlide(i);
      resetAutoSlide();
    });
  });

  heroSlider.addEventListener('mouseenter', () => clearInterval(autoSlideInterval));
  heroSlider.addEventListener('mouseleave', resetAutoSlide);

  autoSlideInterval = setInterval(() => changeSlide(1), 4000);

  console.log("Slider initialized successfully");
});

function startTimer(endTime,id){

function update(){

let now = new Date().getTime()

let distance = endTime - now

let minutes = Math.floor(distance / (1000*60))
let seconds = Math.floor((distance % (1000*60))/1000)

document.getElementById("timer"+id).innerHTML =
minutes + "m " + seconds + "s"

if(distance < 0){
document.getElementById("timer"+id).innerHTML="Auction Ended"
}

}

setInterval(update,1000)

}




document.querySelectorAll('.filter-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
  });
});

// Newsletter form
const newsletterBtn = document.querySelector('.newsletter-form button');
if (newsletterBtn) {
  newsletterBtn.addEventListener('click', () => {
    const input = document.querySelector('.newsletter-form input');
    if (input && input.value.includes('@')) {
      alert('Thanks! You\'ll be notified about new auctions.');
      input.value = '';
    } else {
      alert('Please enter a valid email address.');
    }
  });
}

// Category click → searches that category
function filterCategory(name) {
  window.location.href = '/search?query=' + name;
}

//Timer
document.querySelectorAll('.timer').forEach(timer => {
  let end = new Date(timer.dataset.time).getTime();

  setInterval(() => {
    let now = new Date().getTime();
    let diff = end - now;

    let mins = Math.floor(diff / (1000 * 60));
    timer.innerHTML = mins + " min left";
  }, 1000);
});

function toggleMenu(event) {
    event.stopPropagation();

    const dropdown = document.querySelector('.dropdown');
    dropdown.classList.toggle('show');
}

// Close when clicking outside
document.addEventListener('click', function () {
    const dropdown = document.querySelector('.dropdown');
    dropdown.classList.remove('show');
});
function openReviewModal() {
    document.getElementById("reviewModal").style.display = "block";
}

function closeReviewModal() {
    document.getElementById("reviewModal").style.display = "none";
}

// Close if clicking outside the box
window.onclick = function(event) {
    let modal = document.getElementById("reviewModal");
    if (event.target == modal) {
        closeReviewModal();
    }
}

let currentPosition = 0;

function moveSlide(direction) {
    const track = document.getElementById('testimonialTrack');
    const cards = document.querySelectorAll('.tcard');
    const cardWidth = cards[0].offsetWidth + 20; // Width + Gap
    const visibleCards = window.innerWidth < 900 ? 1 : 3;
    const maxScroll = (cards.length - visibleCards) * cardWidth;

    // Calculate new position
    currentPosition += (direction * cardWidth * -1);

    // Boundary checks
    if (currentPosition > 0) currentPosition = 0;
    if (Math.abs(currentPosition) > maxScroll) currentPosition = -maxScroll;

    track.style.transform = `translateX(${currentPosition}px)`;
}