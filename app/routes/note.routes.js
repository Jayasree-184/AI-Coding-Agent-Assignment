module.exports = (app) => {
    const notes = require('../controllers/note.controller.js');

    // Search Notes — must come BEFORE /notes/:noteId, or Express will treat
    // "search" as a noteId and this route will never be reached.
    app.get('/notes/search', notes.search);

    // Create a new Note
    app.post('/notes', notes.create);

    // Retrieve all Notes
    app.get('/notes', notes.findAll);

    // Retrieve a single Note with noteId
    app.get('/notes/:noteId', notes.findOne);

    // Update a Note with noteId
    app.put('/notes/:noteId', notes.update);

    // Delete a Note with noteId
    app.delete('/notes/:noteId', notes.delete);
};