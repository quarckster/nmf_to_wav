''' Python nmf to wav converter. A structure of nmf file was obtained by
Nice Audio Player decompilation. Using a struct module the script finds raw
audio data and push it through a pipe to ffmpeg.
Usage:
python nmf_converter.py path_to_nmf_file
'''
import os
import sys
import struct
import subprocess

__author__ = "Dmitry Misharov"
__credits__ = "Kirill Yagin"
__email__ = "dmitry.misharov@gmail.com"
__version__ = "0.1"


# Map of types compressions of the nmf file and
# ffmpeg decoders
codecs = {
    0: "g729",
    1: "adpcm_g726",
    2: "adpcm_g726",
	3: "alaw",
    7: "pcm_mulaw",
    8: "g729",
    9: "g723_1",
    10: "g723_1",
    19: "adpcm_g722"
}


def get_packet_header(data):
    "Get required information from packet header."
    return {
        "packet_type": struct.unpack("b", data[0:1])[0],
        "packet_subtype": struct.unpack("h", data[1:3])[0],
        "stream_id": struct.unpack("b", data[3:4])[0],
        "start_time": struct.unpack("d", data[4:12])[0],
        "end_time": struct.unpack("d", data[12:20])[0],
        "packet_size": struct.unpack("I", data[20:24])[0],
        "parameters_size": struct.unpack("I", data[24:28])[0]
    }


def get_compression_type(data):
    "Get compression type of the audio chunk."
    for i in range(0, len(data), 22):
        type_id = struct.unpack("h", data[i:i + 2])[0]
        data_size = struct.unpack("i", data[i + 2:i + 6])[0]
        data = struct.unpack("16s", data[i + 6:i + 22])[0]
        if type_id == 10:
            return get_data_value(data, data_size)


def get_data_value(data, data_size):
    '''The helper function to get value of the data
    field from parameters header.'''
    fmt = "{}s".format(data_size)
    data_value = struct.unpack(fmt, data[0:data_size])
    if data_value == 0:
        data_value = struct.unpack(fmt, data[8:data_size])
    data_value = struct.unpack("b", data_value[0])
    return data_value[0]


def chunks_generator(path_to_file):
    "A python generator of the raw audio data."
    try:
        with open(path_to_file, "rb") as f:
            data = f.read()
    except IOError:
        sys.exit("No such file")
    packet_header_start = 0
    while True:
        packet_header_end = packet_header_start + 28
        headers = get_packet_header(data[packet_header_start:packet_header_end])
        if headers["packet_type"] == 4 and headers["packet_subtype"] == 0:
            chunk_start = packet_header_end + headers["parameters_size"]
            chunk_end = (chunk_start + headers["packet_size"] - headers["parameters_size"])
            chunk_length = chunk_end - chunk_start
            fmt = "{}s".format(chunk_length)
            raw_audio_chunk = struct.unpack(fmt, data[chunk_start:chunk_end])
            yield (get_compression_type(data[packet_header_end:packet_header_end +
                   headers["parameters_size"]]),
                   headers["stream_id"],
                   raw_audio_chunk[0])
        packet_header_start += headers["packet_size"] + 28
        if headers["packet_type"] == 7:
            break


def convert_to_wav(path_to_file):
    "Convert raw audio data using ffmpeg and subprocess."
    previous_stream_id = -1
    processes = {}
    for compression, stream_id, raw_audio_chunk in chunks_generator(path_to_file):
        if stream_id != previous_stream_id and not processes.get(stream_id):
            output_file = os.path.splitext(path_to_file)[0] + "_stream{}".format(stream_id) + ".wav"
            processes[stream_id] = subprocess.Popen(
                ("ffmpeg",
                 "-hide_banner",
                 "-y",
                 "-f",
                 codecs[compression],
                 "-i",
                 "pipe:0",
                 output_file),
                stdin=subprocess.PIPE
            )
            previous_stream_id = stream_id
        processes[stream_id].stdin.write(raw_audio_chunk)
    for key in processes.keys():
        processes[key].stdin.close()
        processes[key].wait()


if __name__ == "__main__":
    try:
        path_to_file = sys.argv[1]
        convert_to_wav(path_to_file)
    except IndexError:
        sys.exit("Please specify path to nmf file")
