const assert = require('node:assert/strict');
const C = require('../docs/finemtec-core.js');
const seed = require('../data_sources/finemtec_financial_history.json');
const financials = Object.fromEntries(['quarterly', 'annual'].map(key => [key, seed[key].map(r => ({...r, revenue:r.revenue_krw/1e8, operating_income:r.operating_income_krw/1e8}))]));
const data = {financials};
const original = JSON.stringify(data);
const quarters = C.financialWindow(data, 'quarterly');
assert.equal(quarters.length, 8);
assert.equal(quarters[0].date, '2024-09-30');
assert.equal(quarters.at(-1).date, '2026-06-30');
assert.equal(C.financialRangeStart(quarters, 'quarterly'), C.timestamp('2024-07-01'));
assert.equal(C.seriesFor('revenue', data, 'quarterly', []).length, 8);
assert.equal(JSON.stringify(data), original, 'presentation must not trim source archive');

const annual = C.financialWindow(data, 'annual');
assert.deepEqual(annual.map(r => r.date.slice(0,4)), ['2021','2022','2023','2024','2025']);
assert.equal(annual[0].revenue, null);
assert.match(annual[0].period_note, /설립 전/);
assert.match(annual[1].period_note, /4개월/);
assert.equal(C.financialRangeStart(annual, 'annual'), C.timestamp('2021-01-01'));

const gap = structuredClone(data);
gap.financials.quarterly = gap.financials.quarterly.filter(r=>r.date!=='2025-03-31').reverse();
const withGap = C.financialWindow(gap, 'quarterly');
assert.equal(withGap.length, 8);
assert.equal(withGap[0].date, '2024-09-30');
assert.equal(withGap[2].date, '2025-03-31');
assert.equal(withGap[2].revenue, null);
assert.match(withGap[2].period_note, /미확보/);

const zero = structuredClone(data);
zero.financials.quarterly.at(-1).operating_income = 0;
zero.financials.annual.push({date:'2026-12-31', revenue:999999, is_estimate:true});
assert.equal(C.seriesFor('operating_income', zero, 'quarterly', []).at(-1).value, 0);
assert.equal(C.financialWindow(zero, 'annual').at(-1).date, '2025-12-31');
assert.deepEqual(C.financialWindow({}, 'quarterly'), []);
assert.equal(C.financialRangeStart([], 'annual'), 0);
const published = require('../docs/data/finemtec.json');
const archive = new Map(published.financials.quarterly.map(row=>[row.date.slice(0,7), row]));
for (const id of ['revenue_yoy', 'opm']) {
  const points = C.seriesFor(id, published, 'quarterly', []);
  assert.equal(points.length, 8);
  assert.equal(points.filter(p=>C.finite(p.value)).length, 8, `${id}: all eight quarters must be numeric`);
  const geometry = C.lineGeometry(points, date=>C.timestamp(date)/86400000, value=>value);
  assert.equal(geometry.vertices.length, 8);
  assert.equal((geometry.path.match(/M/g)||[]).length, 1, `${id}: one connected line`);
  assert.equal((geometry.path.match(/L/g)||[]).length, 7, `${id}: seven links between eight quarters`);
  for (const point of points) {
    const row = archive.get(point.date.slice(0,7));
    const previous = archive.get(`${Number(point.date.slice(0,4))-1}${point.date.slice(4,7)}`);
    const expected = id === 'opm' ? row.operating_income/row.revenue*100 : (row.revenue/previous.revenue-1)*100;
    assert.equal(point.value, Number(expected.toFixed(2)), `${id}: same-quarter YoY / quarterly OPM`);
  }
}
const disconnected = C.lineGeometry([{date:'2026-01-01',value:1},{date:'2026-02-01',value:null},{date:'2026-03-01',value:0}], C.timestamp, value=>value);
assert.equal((disconnected.path.match(/M/g)||[]).length, 2, 'missing data is not interpolated');
assert.equal((disconnected.path.match(/L/g)||[]).length, 0);
console.log('Revenue YoY and OPM: eight numeric quarters joined by seven solid-line segments');
console.log('Fine M-Tec financial windows: 8 quarters / 5 years, gaps and ranges passed');
