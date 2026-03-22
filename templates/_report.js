(function() {
  // 初始化地区分组下拉
  const rows = document.querySelectorAll('#mainTable tbody tr:not(.group-row)');
  const groups = new Set(), cats = new Set(), statuses = new Set();
  rows.forEach(r => {
    if (r.dataset.group) groups.add(r.dataset.group);
    if (r.dataset.cat)   cats.add(r.dataset.cat);
    const badge = r.querySelector('.status-badge');
    if (badge) statuses.add(badge.textContent.trim());
  });

  // 按预设顺序填充地区下拉
  const groupOrder = ["北美","欧洲","日韩","港澳台","东南亚","中东","南美","大洋洲","其他"];
  const fGroup = document.getElementById('fGroup');
  groupOrder.forEach(g => {
    if (groups.has(g)) {
      const o = document.createElement('option');
      o.value = g; o.textContent = g; fGroup.appendChild(o);
    }
  });

  const fill = (sel, vals) => {
    [...vals].filter(Boolean).sort().forEach(v => {
      const o = document.createElement('option');
      o.value = v; o.textContent = v; sel.appendChild(o);
    });
  };
  fill(document.getElementById('fCat'), cats);
  fill(document.getElementById('fStatus'), statuses);
  updateCount();
})();

function applyFilters() {
  const group  = document.getElementById('fGroup').value;
  const cat    = document.getElementById('fCat').value;
  const status = document.getElementById('fStatus').value;
  const kw     = document.getElementById('fKeyword').value.toLowerCase();

  const rows = document.querySelectorAll('#mainTable tbody tr:not(.group-row)');
  const groupVisible = {};
  let visible = 0;

  rows.forEach(r => {
    let show = true;
    if (show && group  && r.dataset.group !== group) show = false;
    if (show && cat    && r.dataset.cat   !== cat)   show = false;
    if (show && status) {
      const badge = r.querySelector('.status-badge');
      if (!badge || badge.textContent.trim() !== status) show = false;
    }
    if (show && kw && !r.textContent.toLowerCase().includes(kw)) show = false;
    r.style.display = show ? '' : 'none';
    if (show) { visible++; groupVisible[r.dataset.group] = true; }
  });

  // 控制分组 header 显隐
  document.querySelectorAll('.group-row').forEach(r => {
    r.style.display = groupVisible[r.dataset.group] ? '' : 'none';
  });

  updateCount(visible);
}

function updateCount(n) {
  const total = document.querySelectorAll('#mainTable tbody tr:not(.group-row)').length;
  const cnt = (n === undefined) ? total : n;
  document.getElementById('resultCount').textContent = `显示 ${cnt} / ${total} 条`;
  document.getElementById('noData').style.display = cnt === 0 ? 'block' : 'none';
}

let _sortDir = {};
function sortTable(col) {
  const tbody = document.querySelector('#mainTable tbody');
  const dataRows = [...tbody.querySelectorAll('tr:not(.group-row)')];
  _sortDir[col] = !_sortDir[col];

  document.querySelectorAll('th').forEach((th, i) => {
    th.classList.toggle('sorted', i === col);
    const icon = th.querySelector('.sort-icon');
    if (icon) icon.textContent = (i === col) ? (_sortDir[col] ? '↑' : '↓') : '⇅';
  });

  // 按列排序（忽略分组 header，排序后重新按分组插入）
  dataRows.sort((a, b) => {
    let va = a.cells[col]?.textContent.trim() ?? '';
    let vb = b.cells[col]?.textContent.trim() ?? '';
    if (col === 3) return _sortDir[col] ? va.localeCompare(vb) : vb.localeCompare(va);
    return _sortDir[col] ? va.localeCompare(vb, 'zh') : vb.localeCompare(va, 'zh');
  });

  // 把分组 header 和对应数据行重新排列
  const groupRows = [...tbody.querySelectorAll('.group-row')];
  const groupOrder = ["北美","欧洲","日韩","港澳台","东南亚","中东","南美","大洋洲","其他"];
  tbody.innerHTML = '';

  groupOrder.forEach(grp => {
    const hdr = groupRows.find(r => r.dataset.group === grp);
    if (!hdr) return;
    const grpDataRows = dataRows.filter(r => r.dataset.group === grp);
    if (grpDataRows.length === 0) return;
    tbody.appendChild(hdr);
    grpDataRows.forEach(r => tbody.appendChild(r));
  });
}