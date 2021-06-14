import os
import sys
from ast import literal_eval
import numpy as np
from PIL import Image
from matplotlib.backend_bases import MouseButton
import matplotlib.pyplot as plt
import matplotlib.patches as patches


def read_header(path):
    with open(path, 'rt') as f:
        data = f.read().splitlines()
    data_list = []
    for line in data:
        if ' = ' in line:
            keyval = line.split(' = ', 1)
            try:
                keyval[1] = literal_eval(
                    keyval[1].replace('{', '[').replace('}', ']'))
            except (SyntaxError, ValueError):
                pass
            data_list.append(keyval)
    
    return dict(data_list)
    
def read_image(path, header):
    # Didn't bother programming for BIP or BIL encoding...
    if header['interleave'] != 'BSQ':
        input('This image is stored in an un-supported interleaved format.\n'
              'Only "BSQ" band sequential images are currently supported.'
              '\n\nPress enter to close.')
        return
    # Likewise with the colour depth. It will only allow 8, 16 or 32.
    dtype_dict = {1: np.uint8,
                  12: np.uint16,
                  13: np.uint32}
    if not header['data type'] in dtype_dict.keys():
        input('This image is stored in an un-supported colour depth.\n'
              'Only 8, 16 or 32 BPC images are currently supported.'
              '\n\nPress enter to close.')
        return

    # Read the image as a 1D numpy array and reshape to a 3D numpy array.
    img = np.fromfile(path, dtype=dtype_dict[header['data type']],
                      offset=header['header offset'])
    try:
        img = np.reshape(img, (header['bands'],
                               header['lines'],
                               header['samples']))
    except ValueError:
        input('The information in the .hdr file does not match the image.\n'
              'Unable to correctly interpret image dimensions.'
              '\n\nPress enter to close.')
        return
    else:
        return img

def save_bands(path, img, header):
    if not os.path.exists(path):
        os.mkdir(path)
    index = 0
    for band_array in img:
        band = Image.fromarray(band_array)
        band.save(os.path.join(path, '{:0>2}'.format(index + 1) + '_'
                               + str(int(header['wavelength'][index]))
                               + header['wavelength units'] + '.tif'))
        index += 1

def plot_bands(img, header):
    # Start selection in middle.
    input_x, input_y = np.shape(img[0])
    input_x, input_y = int(input_x / 2), int(input_y / 2)
    # Make plot.
    plt.style.use('fast')
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 8))
    selection = patches.Circle((input_x, input_y),
                               15, alpha=0.8, fc='yellow')
    ax1.add_patch(selection)
    
    # If suitable wavelengths are available, show a (very approximate)
    # true-colour image on the left. Otherwise just show the first band.
    if header['wavelength units'] == 'nm':
        rgb = []
        for wl in (660, 550, 460):
            rgb.append(header['wavelength'].index(
                min(header['wavelength'], key=lambda x:abs(x - wl))))
        if len(rgb) == len(set(rgb)):
            ax1.imshow(np.stack((img[rgb[0]], img[rgb[1]], img[rgb[2]]),
                                axis=2))
        else:
            ax1.imshow(img[0], cmap='gray')
    else:
        ax1.imshow(img[0], cmap='gray')

    # Produce a list of radiance at each wavelength using an average of the
    # neighbouring pixel values to reduce the effect of noise.
    radiance = []
    for i in img:
        radiance.append(i[input_y - 2:input_y + 3,
                          input_x - 2:input_x + 3].mean())
    # Normalise 0-1.
    radiance = radiance / max(radiance)
    
    # Bar height is governed by relative radiance, bar width by full width
    # at half maximum
    ax2.set_title('Relative spectral radiance', pad=20)
    graph = ax2.bar(x=header['wavelength'],
                    height=radiance,
                    width=header['fwhm'])
    ax2.set_xlabel(f'Wavelength ({header["wavelength units"]})', labelpad=12)
    ax2.set_ylabel('Relative radiance', labelpad=12)

    # Respond to mouse click.
    class EventHandler:
        def __init__(self):
            fig.canvas.mpl_connect('button_press_event', self.on_press)
            self.x0, self.y0 = selection.center

        def on_press(self, event):
            if event.inaxes != ax1:
                return
            if any([event.xdata < 4,
                    event.ydata < 4,
                    event.xdata > np.shape(img[0])[0] - 4,
                    event.ydata > np.shape(img[0])[1] - 4]):
                return

            selection.center = int(event.xdata), int(event.ydata)
            self.x0, self.y0 = selection.center
            radiance = []
            for i in img:
                radiance.append(i[self.y0 - 2:self.y0 + 3,
                                  self.x0 - 2:self.x0 + 3].mean())
            radiance = radiance / max(radiance)
            for bar, h in zip(graph, radiance):
                bar.set_height(h)
            
            fig.canvas.draw()

    handler = EventHandler()
    plt.show()


def run():
    # Check that the input consists of one .raw file only.
    user_input = sys.argv[1:]
    if not user_input:
        input('No input detected. Please drag a .raw file onto the program.'
              '\n\nPress enter to try again.')
        return
    if len(user_input) > 1:
        input('Too many files. Please drag one at a time onto the program.'
              '\n\nPress enter to try again.')
        return
    if not user_input[0].endswith('.raw'):
        input('Input not recognised. Please drag a .raw file onto the program.'
              '\n\nPress enter to try again.')
        return
    image_path = user_input[0]
    
    # Find corresponding header file. Warn if it cannot be found.
    header_path = image_path[:-4] + '.hdr'
    if not os.path.exists(header_path):
        input('No header file detected.\nPlease ensure the .raw file has an '
              'accompanying .hdr file.\nIt should be in the same folder as '
              'the .raw file and have the same filename,\nexcept the '
              'extension, which should be .hdr\n\nPress enter to try again.')
        return

    # Extract all variables from the header file into a dictionary.
    print('Reading image.\n')
    header_dict = read_header(header_path)
    
    # Read the image and store as a numpy array.
    image_array = read_image(image_path, header_dict)
    if image_array is None:
        return

    # Choose to export TIFFs or generate graph.
    while True:
        command = input('Please select an option by typing 1 or 2, then '
                        'press enter.\n\n1: Export all bands as TIFF files.'
                        '\n2: Produce a spectral radiance graph for a given '
                        'pixel.\n\n')
        if not any([command == '1', command == '2']):
            print('\nUnexpected input, please try again.\n')
        else:
            break
    
    # Export TIFFs.
    if command == '1':
        print('\nSaving.\n')
        save_bands(image_path[:-4] + ' bands', image_array, header_dict)
        input('TIFF files saved into new folder.\n\nPress enter to close.')
            
    # Make graph.
    else:
        print('\nOpening graph.')
        plot_bands(image_array, header_dict)
        

if __name__ == '__main__':
    run()
