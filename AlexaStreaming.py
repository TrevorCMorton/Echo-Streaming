import collections
import logging
import random
from copy import copy

from flask import Flask, json
from flaskext.mysql import MySQL
from flask_ask import Ask, question, statement, audio, current_stream, logger

app = Flask(__name__)
ask = Ask(app, "/")
logging.getLogger('flask_ask').setLevel(logging.INFO)

mysql = MySQL()
app.config['MYSQL_DATABASE_USER'] = 'root'
app.config['MYSQL_DATABASE_PASSWORD'] = 'au9Tah3x'
app.config['MYSQL_DATABASE_DB'] = 'SuperCoolDatabase'
app.config['MYSQL_DATABASE_HOST'] = 'supahotfiya.csse.rose-hulman.edu'
mysql.init_app(app)
connection = mysql.connect()
cursor = connection.cursor()



playlist = [
    #'https://drive.google.com/file/d/0B36rBWZuPeUgbWllczBqemQ3c1U/view?usp=sharing',
    #'https://archive.org/download/petescott20160927/20160927%20RC300-53-127.0bpm.mp3',
    #'https://archive.org/download/plpl011/plpl011_05-johnny_ripper-rain.mp3',
    #'https://archive.org/download/piano_by_maxmsp/beats107.mp3',
    #'https://archive.org/download/petescott20160927/20160927%20RC300-58-115.1bpm.mp3',
    #'https://archive.org/download/PianoScale/PianoScale.mp3',
    # 'https://archive.org/download/FemaleVoiceSample/Female_VoiceTalent_demo.mp4',
    #'https://archive.org/download/mailboxbadgerdrumsamplesvolume2/Risset%20Drum%201.mp3',
    #'https://archive.org/download/mailboxbadgerdrumsamplesvolume2/Submarine.mp3',
    # 'https://ia800203.us.archive.org/27/items/CarelessWhisper_435/CarelessWhisper.ogg'
]

class StationManager(object):

    def __init__(self):
        self.station_name = ''

    def set_station(self, cur):
        self.station_name = cur

    def get_station(self):
        return self.station_name

class QueueManager(object):
    """Manages queue data in a seperate context from current_stream.
    The flask-ask Local current_stream refers only to the current data from Alexa requests and Skill Responses.
    Alexa Skills Kit does not provide enqueued or stream-histroy data and does not provide a session attribute
    when delivering AudioPlayer Requests.
    This class is used to maintain accurate control of multiple streams,
    so that the user may send Intents to move throughout a queue.
    """

    def __init__(self, urls):
        self._urls = urls
        self._queued = collections.deque(urls)
        self._history = collections.deque()
        self._current = ""

    @property
    def status(self):
        status = {
            'Current Position': self.current_position,
            'Current URL': self.current,
            'Next URL': self.up_next,
            'Previous': self.previous,
            'History': list(self.history)
        }
        return status

    @property
    def up_next(self):
        """Returns the url at the front of the queue"""
        qcopy = copy(self._queued)
        try:
            return qcopy.popleft()
        except IndexError:
            return None

    @property
    def current(self):
        return self._current

    @current.setter
    def current(self, url):
        self._save_to_history()
        self._current = url

    @property
    def history(self):
        return self._history

    @property
    def previous(self):
        history = copy(self.history)
        try:
            return history.pop()
        except IndexError:
            return None

    def add(self, url):
        self._urls.append(url)
        self._queued.append(url)

    def extend(self, urls):
        self._urls.extend(urls)
        self._queued.extend(urls)

    def _save_to_history(self):
        if self._current:
            self._history.append(self._current)

    def end_current(self):
        self._save_to_history()
        self._current = None

    def step(self):
        self.end_current()
        self._current = self._queued.popleft()
        return self._current

    def step_back(self):
        self._queued.appendleft(self._current)
        self._current = self._history.pop()
        return self._current

    def reset(self):
        self._queued = collections.deque(self._urls)
        self._history = []

    def start(self):
        self.__init__(self._urls)
        return self.step()

    @property
    def current_position(self):
        return len(self._history) + 1

    def empty(self):
        self._urls = []
        self._queued = collections.deque([])
        self._history = collections.deque()


def shuffle(Urls):
    stuffs = []
    for url in Urls:
        stuffs.insert(0, url[0])
        print(url[0])
    random.shuffle(stuffs)
    return stuffs

queue = QueueManager(playlist)
station = StationManager()

@ask.launch
def launch():
    card_title = 'Playlist Example'
    text = 'Welcome to an example for playing a playlist. You can ask me to start the playlist.'
    prompt = 'You can ask start playlist.'
    return question(text).reprompt(prompt).simple_card(card_title, text)

@ask.intent('CreateStationGenreIntent', mapping={'genre': 'Genre'})
def create_station_genre(genre):
    cursor.execute("SELECT Count(GenreName) FROM HasGenre Where GenreName = '{}'".format(genre))
    if cursor.fetchall()[0][0] == 0:
        return statement('sorry bro, we dont have {} on our track mix'.format(genre))
    cursor.execute("SELECT COUNT(StationId) AS Counts FROM Stations WHERE StationName = '{}'".format(genre))
    print(genre)
    num = cursor.fetchall()
    print(num)
    if num[0][0] >= 1:
        print('had it')
        cursor.execute("SELECT Url FROM HaveSong AS t1 INNER JOIN Songs AS t2 ON (t1.SongId = t2.SongId AND t1.StationId = (SELECT StationId FROM Stations WHERE StationName = '{}' AND OwnedBy = 1))".format(genre))
        Urls = cursor.fetchall()
        print(Urls)
        queue.empty()
        songs = shuffle(Urls)
        for i in range(0, len(songs)):
            queue.add(songs[i])
        speech = 'Starting the dankest of {} playlists'.format(genre)
        station.set_station(genre)
        stream_url = queue.start()
        return audio(speech).play(stream_url)
    else:
        print('making it')
        cursor.execute("INSERT INTO Stations (StationName, CreationDate, LastListened, OwnedBy) VALUES ('{}', CURDATE(), CURDATE(), 1)".format(genre))
        print(cursor.fetchall())
        cursor.execute("CALL AddSongToStationGenre('{}', '{}')".format(genre, genre))
        connection.commit()
        print(cursor.fetchall())
        cursor.execute("SELECT Url FROM HaveSong AS t1 INNER JOIN Songs AS t2 ON (t1.SongId = t2.SongId AND t1.StationId = (SELECT StationId FROM Stations WHERE StationName = '{}' AND OwnedBy = 1))".format(genre))
        Urls = cursor.fetchall()
        queue.empty()
        songs = shuffle(Urls)
        for i in range(0, len(songs)):
            queue.add(songs[i])
        #Urls = random.shuffle(Urls)
        speech = 'Starting dis dope {} playlist'.format(genre)
        station.set_station(genre)
        stream_url = queue.start()
        return audio(speech).play(stream_url)

@ask.intent('CreateStationArtistIntent', mapping={'artist': 'Artist'})
def create_station_artist(artist):
    cursor.execute("SELECT Count(ArtistName) FROM Artists Where ArtistName = '{}'".format(artist))
    if cursor.fetchall()[0][0] == 0:
        return statement('sorry bro, we dont have {} on our track mix'.format(artist))
    cursor.execute("SELECT COUNT(StationId) AS Counts FROM Stations WHERE StationName = '{}'".format(artist))
    print(artist)
    num = cursor.fetchall()
    print(num)
    if num[0][0] >= 1:
        print('had it')
        cursor.execute(
            "SELECT Url FROM HaveSong AS t1 INNER JOIN Songs AS t2 ON (t1.SongId = t2.SongId AND t1.StationId = (SELECT StationId FROM Stations WHERE StationName = '{}' AND OwnedBy = 1))".format(
                artist))
        Urls = cursor.fetchall()
        print(Urls)
        queue.empty()
        songs = shuffle(Urls)
        for i in range(0, len(songs)):
            queue.add(songs[i])
        speech = 'Starting the dankest of {} playlists'.format(artist)
        station.set_station(artist)
        stream_url = queue.start()
        return audio(speech).play(stream_url)
    else:
        print('making it')
        cursor.execute(
            "INSERT INTO Stations (StationName, CreationDate, LastListened, OwnedBy) VALUES ('{}', CURDATE(), CURDATE(), 1)".format(
                artist))
        print(cursor.fetchall())
        cursor.execute("CALL AddSongToStationArtist('{}', '{}')".format(artist, artist))
        connection.commit()
        print(cursor.fetchall())
        cursor.execute(
            "SELECT Url FROM HaveSong AS t1 INNER JOIN Songs AS t2 ON (t1.SongId = t2.SongId AND t1.StationId = (SELECT StationId FROM Stations WHERE StationName = '{}' AND OwnedBy = 1))".format(
                artist))
        Urls = cursor.fetchall()
        queue.empty()
        songs = shuffle(Urls)
        for i in range(0, len(songs)):
            queue.add(songs[i])
        # Urls = random.shuffle(Urls)
        speech = 'Starting dis dope {} playlist.'.format(artist)
        station.set_station(artist)
        stream_url = queue.start()
        return audio(speech).play(stream_url)

@ask.intent('CreateStationAlbumIntent', mapping={'album': 'Album'})
def create_station_album(album):
    cursor.execute("SELECT Count(Album) FROM Songs Where Album = '{}'".format(album))
    if cursor.fetchall()[0][0] == 0:
        return statement('sorry bro, we dont have {} on our track mix'.format(album))
    cursor.execute("SELECT COUNT(StationId) AS Counts FROM Stations WHERE StationName = '{}'".format(album))
    print(album)
    num = cursor.fetchall()
    print(num)
    if num[0][0] >= 1:
        print('had it')
        cursor.execute(
            "SELECT Url FROM HaveSong AS t1 INNER JOIN Songs AS t2 ON (t1.SongId = t2.SongId AND t1.StationId = (SELECT StationId FROM Stations WHERE StationName = '{}' AND OwnedBy = 1))".format(
                album))
        Urls = cursor.fetchall()
        print(Urls)
        queue.empty()
        songs = shuffle(Urls)
        for i in range(0, len(songs)):
            queue.add(songs[i])
        speech = 'Starting the dankest of {} playlists'.format(album)
        station.set_station(album)
        stream_url = queue.start()
        return audio(speech).play(stream_url)
    else:
        print('making it')
        cursor.execute(
            "INSERT INTO Stations (StationName, CreationDate, LastListened, OwnedBy) VALUES ('{}', CURDATE(), CURDATE(), 1)".format(
                album))
        print(cursor.fetchall())
        cursor.execute("CALL AddSongToStationAlbum('{}', '{}')".format(album, album))
        connection.commit()
        print(cursor.fetchall())
        cursor.execute(
            "SELECT Url FROM HaveSong AS t1 INNER JOIN Songs AS t2 ON (t1.SongId = t2.SongId AND t1.StationId = (SELECT StationId FROM Stations WHERE StationName = '{}' AND OwnedBy = 1))".format(
                album))
        Urls = cursor.fetchall()
        queue.empty()
        songs = shuffle(Urls)
        for i in range(0, len(songs)):
            queue.add(songs[i])
        # Urls = random.shuffle(Urls)
        speech = 'Starting dis dope {} playlist.'.format(album)
        station.set_station(album)
        stream_url = queue.start()
        return audio(speech).play(stream_url)

@ask.intent('AddToStationGenreIntent', mapping={'genre': 'Genre'})
def add_station_genre(genre):
    print('The Current Station Is {}'.format(station.get_station()))
    name = station.get_station()
    cursor.execute("CALL AddSongToStationGenre('{}', '{}')".format(name, genre))
    connection.commit()
    print(cursor.fetchall())
    cursor.execute(
        "SELECT Url FROM HaveSong AS t1 INNER JOIN Songs AS t2 ON (t1.SongId = t2.SongId AND t1.StationId = (SELECT StationId FROM Stations WHERE StationName = '{}' AND OwnedBy = 1))".format(
            name))
    Urls = cursor.fetchall()
    queue.empty()
    songs = shuffle(Urls)
    for i in range(0, len(songs)):
        queue.add(songs[i])
    # Urls = random.shuffle(Urls)
    speech = 'Dope addition of {} yo'.format(genre)
    stream_url = queue.start()
    return audio(speech).play(stream_url)

@ask.intent('AddToStationArtistIntent', mapping={'artist': 'Artist'})
def add_station_artist(artist):
    print('The Current Station Is {}'.format(station.get_station()))
    name = station.get_station()
    cursor.execute("CALL AddSongToStationArtist('{}', '{}')".format(name, artist))
    connection.commit()
    print(cursor.fetchall())
    cursor.execute(
        "SELECT Url FROM HaveSong AS t1 INNER JOIN Songs AS t2 ON (t1.SongId = t2.SongId AND t1.StationId = (SELECT StationId FROM Stations WHERE StationName = '{}' AND OwnedBy = 1))".format(
            name))
    Urls = cursor.fetchall()
    queue.empty()
    songs = shuffle(Urls)
    for i in range(0, len(songs)):
        queue.add(songs[i])
    # Urls = random.shuffle(Urls)
    speech = 'Dope addition of {} yo'.format(artist)
    stream_url = queue.start()
    return audio(speech).play(stream_url)

@ask.intent('AddToStationAlbumIntent', mapping={'album': 'Album'})
def add_station_album(album):
    print('The Current Station Is {}'.format(station.get_station()))
    name = station.get_station()
    cursor.execute("CALL AddSongToStationAlbum('{}', '{}')".format(name, album))
    connection.commit()
    print(cursor.fetchall())
    cursor.execute(
        "SELECT Url FROM HaveSong AS t1 INNER JOIN Songs AS t2 ON (t1.SongId = t2.SongId AND t1.StationId = (SELECT StationId FROM Stations WHERE StationName = '{}' AND OwnedBy = 1))".format(
            name))
    Urls = cursor.fetchall()
    queue.empty()
    songs = shuffle(Urls)
    for i in range(0, len(songs)):
        queue.add(songs[i])
    # Urls = random.shuffle(Urls)
    speech = 'Dope addition of {} yo'.format(album)
    stream_url = queue.start()
    return audio(speech).play(stream_url)

@ask.intent('RemoveFromStationGenreIntent', mapping={'genre': 'Genre'})
def remove_station_genre(genre):
    print('The Current Station Is {}'.format(station.get_station()))
    name = station.get_station()
    cursor.execute("CALL RemoveSongFromStationGenre('{}', '{}')".format(name, genre))
    connection.commit()
    print(cursor.fetchall())
    cursor.execute(
        "SELECT Url FROM HaveSong AS t1 INNER JOIN Songs AS t2 ON (t1.SongId = t2.SongId AND t1.StationId = (SELECT StationId FROM Stations WHERE StationName = '{}' AND OwnedBy = 1))".format(
            name))
    Urls = cursor.fetchall()
    queue.empty()
    songs = shuffle(Urls)
    for i in range(0, len(songs)):
        queue.add(songs[i])
    # Urls = random.shuffle(Urls)
    speech = 'Those were trash any way, man'
    stream_url = queue.start()
    return audio(speech).play(stream_url)

@ask.intent('RemoveFromStationArtistIntent', mapping={'artist': 'Artist'})
def remove_station_artist(artist):
    print('The Current Station Is {}'.format(station.get_station()))
    name = station.get_station()
    cursor.execute("CALL RemoveSongFromStationArtist('{}', '{}')".format(name, artist))
    connection.commit()
    print(cursor.fetchall())
    cursor.execute(
        "SELECT Url FROM HaveSong AS t1 INNER JOIN Songs AS t2 ON (t1.SongId = t2.SongId AND t1.StationId = (SELECT StationId FROM Stations WHERE StationName = '{}' AND OwnedBy = 1))".format(
            name))
    Urls = cursor.fetchall()
    queue.empty()
    songs = shuffle(Urls)
    for i in range(0, len(songs)):
        queue.add(songs[i])
    # Urls = random.shuffle(Urls)
    speech = 'Those were trash any way, man'
    stream_url = queue.start()
    return audio(speech).play(stream_url)

@ask.intent('RemoveFromStationAlbumIntent', mapping={'album': 'Album'})
def remove_station_album(album):
    print('The Current Station Is {}'.format(station.get_station()))
    name = station.get_station()
    cursor.execute("CALL RemoveSongFromStationAlbum('{}', '{}')".format(name, album))
    connection.commit()
    print(cursor.fetchall())
    cursor.execute(
        "SELECT Url FROM HaveSong AS t1 INNER JOIN Songs AS t2 ON (t1.SongId = t2.SongId AND t1.StationId = (SELECT StationId FROM Stations WHERE StationName = '{}' AND OwnedBy = 1))".format(
            name))
    Urls = cursor.fetchall()
    queue.empty()
    songs = shuffle(Urls)
    for i in range(0, len(songs)):
        queue.add(songs[i])
    # Urls = random.shuffle(Urls)
    speech = 'Those were trash any way, man'
    stream_url = queue.start()
    return audio(speech).play(stream_url)

@ask.intent('RenameCurrentStationIntent')
def rename_station():
    return statement('Sorry, this is not implemented yet')

@ask.intent('LikeCurrentSongIntent')
def like_current_song():
    cursor.execute("CALL LikeASong('User', '{}')".format(queue.current))
    connection.commit()
    return statement('cool story bro')

@ask.intent('DislikeCurrentSongIntent')
def dislike_current_song():
    cursor.execute("CALL DislikeASong('User', '{}')".format(queue.current))
    connection.commit()
    return statement('well, piss off bro')

@ask.intent('LikeCurrentArtistIntent')
def like_current_artist():
    cursor.execute("CALL LikeAArtist('User', '{}')".format(queue.current))
    connection.commit()
    return statement('hell yeah, they are the tits')


# QueueManager object is not stepped forward here.
# This allows for Next Intents and on_playback_finished requests to trigger the step
@ask.on_playback_nearly_finished()
def nearly_finished():
    if queue.up_next:
        _infodump('Alexa is now ready for a Next or Previous Intent')
        # dump_stream_info()
        next_stream = queue.up_next
        _infodump('Enqueueing {}'.format(next_stream))
        return audio().enqueue(next_stream)
    else:
        _infodump('Nearly finished with last song in playlist')


@ask.on_playback_finished()
def play_back_finished():
    _infodump('Finished Audio stream for track {}'.format(queue.current_position))
    if queue.up_next:
        queue.step()
        _infodump('stepped queue forward')
        dump_stream_info()
    else:
        return statement('You have reached the end of the Station')


# NextIntent steps queue forward and clears enqueued streams that were already sent to Alexa
# next_stream will match queue.up_next and enqueue Alexa with the correct subsequent stream.
@ask.intent('AMAZON.NextIntent')
def next_song():
    if queue.up_next:
        speech = ''
        next_stream = queue.step()
        _infodump('Stepped queue forward to {}'.format(next_stream))
        dump_stream_info()
        return audio(speech).play(next_stream)
    else:
        return audio('There are no more songs in the queue')


@ask.intent('AMAZON.PreviousIntent')
def previous_song():
    if queue.previous:
        speech = 'playing previously played song'
        prev_stream = queue.step_back()
        dump_stream_info()
        return audio(speech).play(prev_stream)

    else:
        return audio('There are no songs in your playlist history.')


@ask.intent('AMAZON.StartOverIntent')
def restart_track():
    if queue.current:
        speech = 'Restarting current track'
        dump_stream_info()
        return audio(speech).play(queue.current, offset=0)
    else:
        return statement('There is no current song')


@ask.on_playback_started()
def started(offset, token, url):
    _infodump('Started audio stream for track {}'.format(queue.current_position))
    dump_stream_info()


@ask.on_playback_stopped()
def stopped(offset, token):
    _infodump('Stopped audio stream for track {}'.format(queue.current_position))

@ask.intent('AMAZON.PauseIntent')
def pause():
    seconds = current_stream.offsetInMilliseconds / 1000
    msg = 'Paused the Playlist'
    _infodump(msg)
    dump_stream_info()
    return audio(msg).stop().simple_card(msg)


@ask.intent('AMAZON.ResumeIntent')
def resume():
    seconds = current_stream.offsetInMilliseconds / 1000
    msg = 'Resuming the Playlist'
    _infodump(msg)
    dump_stream_info()
    return audio(msg).resume().simple_card(msg)


@ask.session_ended
def session_ended():
    return "", 200

def dump_stream_info():
    status = {
        'Current Stream Status': current_stream.__dict__,
        'Queue status': queue.status
    }
    _infodump(status)


def _infodump(obj, indent=2):
    msg = json.dumps(obj, indent=indent)
    logger.info(msg)


if __name__ == '__main__':
    app.run(debug=True)