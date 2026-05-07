// Baan Na Resort - Interactive Room Map Logic

document.addEventListener('DOMContentLoaded', function() {
    // Set default date to today and prevent past date selection
    const today = new Date();
    // Format YYYY-MM-DD in local time
    const yyyy = today.getFullYear();
    const mm = String(today.getMonth() + 1).padStart(2, '0');
    const dd = String(today.getDate()).padStart(2, '0');
    const todayStr = `${yyyy}-${mm}-${dd}`;
    
    // Tomorrow
    const tomorrow = new Date(today);
    tomorrow.setDate(tomorrow.getDate() + 1);
    const t_yyyy = tomorrow.getFullYear();
    const t_mm = String(tomorrow.getMonth() + 1).padStart(2, '0');
    const t_dd = String(tomorrow.getDate()).padStart(2, '0');
    const tomorrowStr = `${t_yyyy}-${t_mm}-${t_dd}`;
    
    const searchCheckin = document.getElementById('search-checkin');
    if (searchCheckin) {
        searchCheckin.value = todayStr;
        searchCheckin.min = todayStr;
    }
    
    const searchCheckout = document.getElementById('search-checkout');
    if (searchCheckout) {
        searchCheckout.value = tomorrowStr;
        searchCheckout.min = todayStr;
    }

    const modalCheckin = document.querySelector('input[name="checkin_date"]');
    if (modalCheckin) {
        modalCheckin.min = todayStr;
    }
    const modalCheckout = document.querySelector('input[name="checkout_date"]');
    if (modalCheckout) {
        modalCheckout.min = todayStr;
    }

    // Automatically check availability for today
    checkAvailability();
});

async function renderMap(unavailableIds = null, unavailableStatus = null) {
    const mapEl = document.getElementById('resort-map');

    try {
        const response = await fetch('/api/rooms');
        const rooms = await response.json();
        
        if (mapEl) {
            mapEl.innerHTML = ''; // Clear map

            rooms.forEach(room => {
                const coords = room.map_coords || { x: 0, y: 0 };
                const marker = document.createElement('div');
                
                // If we are checking availability for specific dates, 
                // the status depends on the unavailableIds list.
                let displayStatus = room.status;
                if (unavailableIds !== null) {
                    if (room.status === 'maintenance') {
                        displayStatus = 'maintenance';
                    } else if (unavailableIds.includes(room.id)) {
                        displayStatus = (unavailableStatus && unavailableStatus[room.id]) ? unavailableStatus[room.id] : 'R';
                    } else {
                        displayStatus = 'I';
                    }
                }

                marker.className = `room-marker ${displayStatus}`;
                marker.style.left = `calc(${coords.x}% - 30px)`;
                marker.style.top = `calc(${coords.y}% - 30px)`;
                marker.innerText = coords.label || room.room_number || room.id;
                
                marker.onclick = () => showRoomDetails(room);
                
                mapEl.appendChild(marker);
            });
        }

        // Also render the room grid cards
        renderRoomGrid(rooms, unavailableIds, unavailableStatus);
    } catch (error) {
        console.error('Error loading rooms:', error);
    }
}

function renderRoomGrid(rooms, unavailableIds = null, unavailableStatus = null, currentPage = 1) {
    const containerEl = document.getElementById('room-grid-container');
    if (!containerEl) return;

    // Pagination Logic
    let pages = [];
    let unassignedRooms = [...rooms];
    
    while(unassignedRooms.length > 0) {
        let page = [];
        let typeCounts = {};
        let leftover = [];
        
        for (let r of unassignedRooms) {
            if (page.length >= 15) {
                leftover.push(r);
                continue;
            }
            let tName = (r.resort_types && r.resort_types.name) ? r.resort_types.name : 'บ้านพักอื่นๆ';
            let count = typeCounts[tName] || 0;
            
            if (count < 5) {
                page.push(r);
                typeCounts[tName] = count + 1;
            } else {
                leftover.push(r);
            }
        }
        pages.push(page);
        unassignedRooms = leftover;
    }
    
    let totalPages = pages.length;
    if (currentPage < 1) currentPage = 1;
    if (totalPages > 0 && currentPage > totalPages) currentPage = totalPages;
    
    let currentRooms = pages.length > 0 ? pages[currentPage - 1] : [];

    containerEl.innerHTML = ''; // Clear container

    // Group currentRooms by resort_type
    const groupedRooms = {};
    currentRooms.forEach(room => {
        const typeName = (room.resort_types && room.resort_types.name) ? room.resort_types.name : 'บ้านพักอื่นๆ';
        if (!groupedRooms[typeName]) groupedRooms[typeName] = [];
        groupedRooms[typeName].push(room);
    });

    Object.keys(groupedRooms).forEach(typeName => {
        // Header
        const header = document.createElement('h3');
        header.style.cssText = 'color: var(--primary); font-size: 1.3rem; margin-top: 1.5rem; margin-bottom: 1rem; border-bottom: 1px solid #e2e8f0; padding-bottom: 0.3rem; width: 100%;';
        header.innerText = `🏡 ${typeName}`;
        containerEl.appendChild(header);

        // Grid
        const subGrid = document.createElement('div');
        subGrid.className = 'room-grid';
        subGrid.style.marginBottom = '2rem';

        groupedRooms[typeName].forEach(room => {
            let displayStatus = room.status;
            if (unavailableIds !== null) {
                if (room.status === 'maintenance') {
                    displayStatus = 'maintenance';
                } else if (unavailableIds.includes(room.id)) {
                    displayStatus = (unavailableStatus && unavailableStatus[room.id]) ? unavailableStatus[room.id] : 'R';
                } else {
                    displayStatus = 'I';
                }
            }

            const card = document.createElement('div');
            card.className = 'room-item-card';

            const mainImg = room.images && room.images.length > 0 ? room.images[0] : 'https://images.unsplash.com/photo-1566073771259-6a8506099945?ixlib=rb-1.2.1&auto=format&fit=crop&w=800&q=80';
            
            let statusBadge = '';
            if (displayStatus === 'R') statusBadge = '<span class="room-card-status" style="background:#fee2e2; color:#ef4444;">ติดจอง</span>';
            else if (displayStatus === 'O') statusBadge = '<span class="room-card-status" style="background:#fee2e2; color:#ef4444;">ไม่ว่าง</span>';
            else if (displayStatus === 'maintenance') statusBadge = '<span class="room-card-status" style="background:#fef3c7; color:#d97706;">ปรับปรุง</span>';
            else statusBadge = '<span class="room-card-status" style="background:#f0fdf4; color:#22c55e;">ว่าง</span>';

            card.innerHTML = `
                <div class="room-card-image">
                    ${statusBadge}
                    <img src="${mainImg}" alt="${room.name}">
                    <div class="room-card-price">฿${room.price.toLocaleString()} / คืน</div>
                </div>
                <div class="room-card-content">
                    <div class="room-card-title">${room.name}</div>
                    <div class="room-card-info">
                        <span>${room.room_number ? '#' + room.room_number : ''}</span>
                        <span>${room.bed_type === 'double' ? '🛌 เตียงคู่' : '👤 เตียงเดียว'}</span>
                    </div>
                    <div class="room-card-desc">${room.description || 'สัมผัสประสบการณ์การพักผ่อนที่หรูหราท่ามกลางธรรมชาติที่บ้านนารีสอร์ท'}</div>
                    <div class="room-card-footer">
                        <button class="btn-book" onclick='showRoomDetails(${JSON.stringify(room)})' style="background-color: var(--status-available);">
                            คลิ๊กดูรายละเอียด
                        </button>
                    </div>
                </div>
            `;
            // Make the whole card clickable
            card.onclick = () => showRoomDetails(room);
            subGrid.appendChild(card);
        });

        containerEl.appendChild(subGrid);
    });

    // Pagination controls
    if (totalPages > 1) {
        let paginationDiv = document.createElement('div');
        paginationDiv.className = 'pagination';
        paginationDiv.style.cssText = 'display: flex; justify-content: center; gap: 0.5rem; margin-top: 2rem; width: 100%;';
        
        if (currentPage > 1) {
            let prev = document.createElement('button');
            prev.innerText = '« ก่อนหน้า';
            prev.className = 'btn btn-outline';
            prev.style.cssText = 'padding: 0.5rem 1rem; border: 1px solid var(--primary); color: var(--primary); background: transparent; cursor: pointer; border-radius: 5px;';
            prev.onclick = () => {
                renderRoomGrid(rooms, unavailableIds, unavailableStatus, currentPage - 1);
                document.getElementById('room-listing-section').scrollIntoView({ behavior: 'smooth' });
            };
            paginationDiv.appendChild(prev);
        }
        
        for (let p = 1; p <= totalPages; p++) {
            let btn = document.createElement('button');
            btn.innerText = p;
            if (p === currentPage) {
                btn.className = 'btn btn-primary';
                btn.style.cssText = 'padding: 0.5rem 1rem; background: var(--primary); color: white; border: none; border-radius: 5px; cursor: default;';
            } else {
                btn.className = 'btn btn-outline';
                btn.style.cssText = 'padding: 0.5rem 1rem; border: 1px solid var(--primary); color: var(--primary); background: transparent; cursor: pointer; border-radius: 5px;';
                btn.onclick = () => {
                    renderRoomGrid(rooms, unavailableIds, unavailableStatus, p);
                    document.getElementById('room-listing-section').scrollIntoView({ behavior: 'smooth' });
                };
            }
            paginationDiv.appendChild(btn);
        }
        
        if (currentPage < totalPages) {
            let next = document.createElement('button');
            next.innerText = 'ถัดไป »';
            next.className = 'btn btn-outline';
            next.style.cssText = 'padding: 0.5rem 1rem; border: 1px solid var(--primary); color: var(--primary); background: transparent; cursor: pointer; border-radius: 5px;';
            next.onclick = () => {
                renderRoomGrid(rooms, unavailableIds, unavailableStatus, currentPage + 1);
                document.getElementById('room-listing-section').scrollIntoView({ behavior: 'smooth' });
            };
            paginationDiv.appendChild(next);
        }
        
        containerEl.appendChild(paginationDiv);
    }
}

async function checkAvailability() {
    const checkinEl = document.getElementById('search-checkin');
    const checkoutEl = document.getElementById('search-checkout');
    const statusMsg = document.getElementById('availability-status');

    if (!checkinEl || !checkoutEl) {
        renderMap();
        return;
    }

    const checkin = checkinEl.value;
    const checkout = checkoutEl.value;

    if (!checkin || !checkout) {
        alert('กรุณาเลือกวันที่เช็คอินและเช็คเอาท์ครับ');
        return;
    }

    if (new Date(checkin) >= new Date(checkout)) {
        alert('วันที่เช็คเอาท์ต้องอยู่หลังจากวันที่เช็คอินครับ');
        return;
    }

    if (statusMsg) {
        statusMsg.innerText = `🔄 กำลังตรวจสอบห้องว่างตั้งแต่วันที่ ${checkin} ถึง ${checkout}...`;
        statusMsg.style.color = 'var(--primary)';
    }

    try {
        const response = await fetch('/api/check_availability', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ checkin, checkout })
        });
        const result = await response.json();
        
        if (result.unavailable_ids) {
            // Store globally for showRoomDetails
            window.lastSearch = {
                ids: result.unavailable_ids,
                status: result.unavailable_status,
                checkin,
                checkout
            };
            
            renderMap(result.unavailable_ids, result.unavailable_status);
            
            // Fix: Also update the grid cards
            const roomsResponse = await fetch('/api/rooms');
            const rooms = await roomsResponse.json();
            renderRoomGrid(rooms, result.unavailable_ids, result.unavailable_status);
            
            if (statusMsg) {
                statusMsg.innerHTML = `✅ ตรวจสอบเสร็จสิ้น: แสดงห้องว่างของวันที่ <b>${checkin}</b> ถึง <b>${checkout}</b>`;
            }
        }
    } catch (error) {
        console.error('Error checking availability:', error);
        if (statusMsg) {
            statusMsg.innerText = '❌ เกิดข้อผิดพลาดในการตรวจสอบ กรุณาลองใหม่อีกครั้ง';
            statusMsg.style.color = 'red';
        }
    }
}

function showRoomDetails(room) {
    const checkinSearch = document.getElementById('search-checkin')?.value;
    const checkoutSearch = document.getElementById('search-checkout')?.value;
    
    let displayStatus = room.status;
    
    // If a search was performed, use the searched availability
    if (window.lastSearch && checkinSearch && checkoutSearch) {
        if (room.status === 'maintenance') {
            displayStatus = 'maintenance';
        } else if (window.lastSearch.ids.includes(room.id)) {
            displayStatus = window.lastSearch.status[room.id] || 'R';
        } else {
            displayStatus = 'I';
        }
    }

    if (displayStatus === 'R') {
        alert('ขออภัยครับ ห้องนี้มีการจองเข้ามาแล้ว (รอชำระเงิน)');
        return;
    }
    if (displayStatus === 'O') {
        alert('ขออภัยครับ ห้องนี้มีผู้เข้าพักแล้วในวันที่คุณเลือก');
        return;
    }
    if (displayStatus === 'maintenance') {
        alert('ห้องนี้กำลังอยู่ระหว่างการปรับปรุง ขออภัยในความไม่สะดวกครับ');
        return;
    }

    const modal = document.getElementById('room-modal');
    if (!modal) return;
    
    document.getElementById('modal-room-name').innerText = room.name;
    document.getElementById('modal-room-number').innerText = room.room_number ? `#${room.room_number}` : '';
    document.getElementById('modal-room-desc').innerText = room.description || '';
    document.getElementById('modal-room-price').innerText = room.price.toLocaleString();
    document.getElementById('modal-room-id').value = room.id;
    
    // Auto-fill dates from search bar
    if (checkinSearch) document.getElementsByName('checkin_date')[0].value = checkinSearch;
    if (checkoutSearch) document.getElementsByName('checkout_date')[0].value = checkoutSearch;
    
    // Bed type display
    const bedTypeEl = document.getElementById('modal-bed-type');
    if (bedTypeEl) {
        bedTypeEl.innerHTML = room.bed_type === 'double' ? '🛌 เตียงคู่' : '👤 เตียงเดียว';
    }

    modal.style.display = 'block';

    // Gallery Logic
    const mainImg = document.getElementById('modal-main-img');
    const thumbRow = document.getElementById('thumbnail-row');
    const galleryContainer = document.getElementById('room-gallery-container');

    if (room.images && room.images.length > 0) {
        galleryContainer.style.display = 'block';
        mainImg.src = room.images[0];
        
        // Modal image click -> Lightbox
        mainImg.onclick = () => window.open(mainImg.src, '_blank');

        // Thumbnails
        thumbRow.innerHTML = '';
        room.images.forEach((imgUrl, index) => {
            const thumb = document.createElement('img');
            thumb.src = imgUrl;
            thumb.style.cssText = 'width: 60px; height: 50px; object-fit: cover; border-radius: 6px; cursor: pointer; border: 2px solid transparent; flex-shrink: 0;';
            if (index === 0) thumb.style.borderColor = 'var(--primary)';
            
            thumb.onclick = () => {
                mainImg.src = imgUrl;
                Array.from(thumbRow.children).forEach(t => t.style.borderColor = 'transparent');
                thumb.style.borderColor = 'var(--primary)';
            };
            thumbRow.appendChild(thumb);
        });
    } else {
        galleryContainer.style.display = 'none';
        mainImg.src = '';
    }

    modal.style.display = 'flex';
}

function closeModal() {
    document.getElementById('room-modal').style.display = 'none';
}

// Close modal when clicking outside
window.onclick = function(event) {
    const modal = document.getElementById('room-modal');
    if (event.target == modal) {
        modal.style.display = "none";
    }
}
