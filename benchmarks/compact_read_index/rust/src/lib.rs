//! Compact sorted byte postings. Python owns artifact identity and trust.
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyBytes;

const MAGIC: &[u8; 8] = b"DMIDX001";
const HEADER: usize = 12;
const ENTRY: usize = 12;

fn invalid() -> PyErr {
    PyValueError::new_err("invalid compact read index")
}

fn word(data: &[u8], at: usize) -> Option<usize> {
    let bytes = data.get(at..at.checked_add(4)?)?.try_into().ok()?;
    Some(u32::from_le_bytes(bytes) as usize)
}

fn put(data: &mut Vec<u8>, value: usize) -> PyResult<()> {
    let value = u32::try_from(value).map_err(|_| invalid())?;
    data.extend(value.to_le_bytes());
    Ok(())
}

#[pyfunction]
fn build<'py>(
    py: Python<'py>,
    mut rows: Vec<(Vec<u8>, Vec<u8>)>,
) -> PyResult<Bound<'py, PyBytes>> {
    rows.sort_unstable_by(|a, b| a.0.cmp(&b.0));
    let directory_end = rows.len().checked_mul(ENTRY)
        .and_then(|size| size.checked_add(HEADER)).ok_or_else(invalid)?;
    let mut directory = Vec::new();
    directory.extend(MAGIC);
    put(&mut directory, rows.len())?;
    let mut contents = Vec::new();
    let mut previous: Option<&[u8]> = None;
    for (key, value) in &rows {
        if key.is_empty() || previous == Some(key) {
            return Err(invalid());
        }
        previous = Some(key);
        put(&mut directory, directory_end + contents.len())?;
        contents.extend_from_slice(key);
        put(&mut directory, directory_end + contents.len())?;
        contents.extend_from_slice(value);
        put(&mut directory, directory_end + contents.len())?;
    }
    directory.extend(contents);
    Ok(PyBytes::new(py, &directory))
}

#[pyclass(frozen)]
struct Index {
    // Immutable Python bytes are shared with the caller without copying them.
    data: Py<PyBytes>,
    count: usize,
}

fn row(data: &[u8], index: usize) -> Option<(&[u8], &[u8])> {
    let at = HEADER.checked_add(index.checked_mul(ENTRY)?)?;
    let start = word(data, at)?;
    let middle = word(data, at + 4)?;
    let end = word(data, at + 8)?;
    if start >= middle {
        return None;
    }
    Some((data.get(start..middle)?, data.get(middle..end)?))
}

#[pymethods]
impl Index {
    #[new]
    fn new(data: Bound<'_, PyBytes>) -> PyResult<Self> {
        let bytes = data.as_bytes();
        if !bytes.starts_with(MAGIC) {
            return Err(invalid());
        }
        let count = word(bytes, 8).ok_or_else(invalid)?;
        let mut end = count.checked_mul(ENTRY)
            .and_then(|size| size.checked_add(HEADER)).ok_or_else(invalid)?;
        if end > bytes.len() {
            return Err(invalid());
        }
        let mut previous: Option<&[u8]> = None;
        for index in 0..count {
            if word(bytes, HEADER + index * ENTRY) != Some(end) {
                return Err(invalid());
            }
            let (key, value) = row(bytes, index).ok_or_else(invalid)?;
            if previous.is_some_and(|p| p >= key) {
                return Err(invalid());
            }
            previous = Some(key);
            end += key.len() + value.len();
        }
        if end != bytes.len() {
            return Err(invalid());
        }
        Ok(Self { data: data.unbind(), count })
    }

    fn get<'py>(&self, py: Python<'py>, key: &[u8]) -> Option<Bound<'py, PyBytes>> {
        let data = self.data.bind(py).as_bytes();
        let (mut start, mut end) = (0, self.count);
        while start < end {
            let mid = start + (end - start) / 2;
            let (candidate, value) = row(data, mid)?;
            match candidate.cmp(key) {
                std::cmp::Ordering::Less => start = mid + 1,
                std::cmp::Ordering::Greater => end = mid,
                std::cmp::Ordering::Equal => return Some(PyBytes::new(py, value)),
            }
        }
        None
    }

    fn keys<'py>(&self, py: Python<'py>, prefix: &[u8]) -> Vec<Bound<'py, PyBytes>> {
        let data = self.data.bind(py).as_bytes();
        (0..self.count)
            .filter_map(|i| row(data, i)?.0.strip_prefix(prefix))
            .map(|key| PyBytes::new(py, key))
            .collect()
    }

    fn __len__(&self) -> usize {
        self.count
    }
}

#[pymodule]
fn _dm_compact_read_index(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(build, module)?)?;
    module.add_class::<Index>()?;
    Ok(())
}
