const currentDate = document.querySelector(".current-date"),
daysTag = document.querySelector(".days");
prevNextIcon = document.querySelectorAll(".icons span");

let date= new Date(),
currYear = date.getFullYear(),
currMonth = date.getMonth();

const months = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

const renderCalendar = (classId = currentClassId) => {
    if (classId) {
        currentClassId = classId;  // Update the global classId
    }

    let firstDateofMonth = new Date(currYear, currMonth, 1).getDay(),
        lastDateofMonth = new Date(currYear, currMonth + 1, 0).getDate(),
        lastDayofMonth = new Date(currYear, currMonth, lastDateofMonth).getDay(),
        lastDateofLastMonth = new Date(currYear, currMonth, 0).getDate();
    let liTag = "";

    for (let i = firstDateofMonth; i > 0; i--) {
        let prevMonthDate = `${currYear}-${String(currMonth).padStart(2, '0')}-${String(lastDateofLastMonth - i + 1).padStart(2, '0')}`;
        liTag += `<li class="inactive" data-date="${prevMonthDate}">${lastDateofLastMonth - i + 1}</li>`;
    }

    for (let i = 1; i <= lastDateofMonth; i++) {
        let isToday = i === date.getDate() && currMonth === new Date().getMonth() && currYear === new Date().getFullYear() ? "active" : "";
        let currentMonthDate = `${currYear}-${String(currMonth + 1).padStart(2, '0')}-${String(i).padStart(2, '0')}`;
        liTag += `<li class="${isToday}" data-date="${currentMonthDate}">${i}</li>`;
    }

    for (let i = lastDayofMonth; i < 6; i++) {
        let nextMonthDate = `${currYear}-${String(currMonth + 2).padStart(2, '0')}-${String(i - lastDayofMonth + 1).padStart(2, '0')}`;
        liTag += `<li class="inactive" data-date="${nextMonthDate}">${i - lastDayofMonth + 1}</li>`;
    }

    currentDate.innerText = `${months[currMonth]} ${currYear}`;
    daysTag.innerHTML = liTag;

    // Add click event listener to each day
    document.querySelectorAll('.days li').forEach(item => {
        item.addEventListener('click', () => {
            let selectedDate = item.getAttribute('data-date');
            fetchAttendanceData(currentClassId, selectedDate);  // Use currentClassId in fetchAttendanceData
        });
    });
};

prevNextIcon.forEach(icon => {
    icon.addEventListener("click", () => {
        currMonth = icon.id === "prev" ? currMonth - 1 : currMonth + 1;

        if (currMonth < 0) {
            currMonth = 11; // Wrap around to December
            currYear--; // Decrement year
        } else if (currMonth > 11) {
            currMonth = 0; // Wrap around to January
            currYear++; // Increment year
        }
        renderCalendar(currentClassId);  // Pass currentClassId to renderCalendar
    });
});

renderCalendar();  // Initial call to render calendar