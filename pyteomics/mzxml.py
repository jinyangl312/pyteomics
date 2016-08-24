from pyteomics import xml, auxiliary as aux
import base64
import zlib
import struct
import numpy as np


def _decode_peaks(info, peaks_data):
    """Decode the interleaved base 64 encoded, potentially
    compressed, raw data points.

    Parameters
    ----------
    info : dict
        The current context
    peaks_data : str
        The textually encoded peak data

    Returns
    -------
    tuple of np.array
        A pair of NumPy arrays containing
        m/z and intensity values.
    """
    content = peaks_data.encode('ascii')
    data = base64.b64decode(content)
    if info.get('compressionType') == 'zlib':
        data = zlib.decompress(data)
    if info['precision'] == "32":
        prec = 4
    else:
        prec = 8
    width = len(data) / prec
    unpacked = struct.unpack(">%dL" % width, data)
    mzs = []
    intensities = []
    i = 0
    for d in unpacked:
        v = struct.unpack("f", struct.pack("I", d))[0]
        if i % 2 == 0:
            mzs.append(v)
        else:
            intensities.append(v)
        i += 1
    return np.array(mzs), np.array(intensities)


class MzXML(xml.IndexedXML):
    _root_element = "mzXML"
    _default_iter_tag = 'scan'
    _indexed_tags = {'scan'}
    _indexed_tag_keys = {'scan': 'num'}
    _default_version = None
    _default_schema = {'bools': {('dataProcessing', 'centroided'),
                                 ('dataProcessing', 'chargeDeconvoluted'),
                                 ('dataProcessing', 'deisotoped'),
                                 ('dataProcessing', 'spotIntegration'),
                                 ('maldi', 'collisionGas'),
                                 ('scan', 'centroided'),
                                 ('scan', 'chargeDeconvoluted'),
                                 ('scan', 'deisotoped')},
                       'charlists': set(),
                       'floatlists': set(),
                       'floats': {('dataProcessing', 'intensityCutoff'),
                                  ('precursorMz', 'precursorIntensity'),
                                  ('precursorMz', 'windowWideness'),
                                  ('precursorMz', 'precursorMz'),
                                  ('scan', 'basePeakIntensity'),
                                  ('scan', 'basePeakMz'),
                                  ('scan', 'cidGasPressure'),
                                  ('scan', 'collisionEnergy'),
                                  ('scan', 'compensationVoltage'),
                                  ('scan', 'endMz'),
                                  ('scan', 'highMz'),
                                  ('scan', 'ionisationEnergy'),
                                  ('scan', 'lowMz'),
                                  ('scan', 'startMz'),
                                  ('scan', 'totIonCurrent')},
                       'intlists': set(),
                       'ints': {('msInstrument', 'msInstrumentID'),
                                ('peaks', 'compressedLen'),
                                ('robot', 'deadVolume'),
                                ('scan', 'msInstrumentID'),
                                ('scan', 'peaksCount'),
                                ('scanOrigin', 'num')},
                       'lists': {'dataProcessing',
                                 'msInstrument',
                                 'parentFile',
                                 'peaks',
                                 'plate',
                                 'precursorMz',
                                 'scanOrigin',
                                 'spot'}}

    def _get_info_smart(self, element, **kw):
        name = xml._local_name(element)
        kwargs = dict(kw)
        rec = kwargs.pop('recursive', None)
        if name in {'mzXML'}:
            info = self._get_info(element,
                                  recursive=(
                                      rec if rec is not None else False),
                                  **kwargs)
        else:
            info = self._get_info(element,
                                  recursive=(rec if rec is not None else True),
                                  **kwargs)
        if "num" in info:
            info['id'] = info['num']
        if 'peaks' in info:
            if not isinstance(info['peaks'], (dict, list)):
                mz_array, intensity_array = _decode_peaks(
                    info, info.pop('peaks'))
                info['m/z array'] = mz_array
                info['intensity array'] = intensity_array
            else:
                peaks_data = info.pop('peaks')[0]
                try:
                    info['m/z array'] = peaks_data['m/z array']
                    info['intensity array'] = peaks_data['intensity array']
                except KeyError:
                    info['m/z array'] = np.array()
                    info['intensity array'] = np.array()

        if "retentionTime" in info:
            info['retentionTime'] = float(info['retentionTime'].strip('PTS'))
        return info


def read(source, read_schema=True, iterative=True, use_index=False, dtype=None):
    """Parse `source` and iterate through spectra.

    Parameters
    ----------
    source : str or file
        A path to a target mzML file or the file object itself.

    read_schema : bool, optional
        If :py:const:`True`, attempt to extract information from the XML schema
        mentioned in the mzML header (default). Otherwise, use default
        parameters. Disable this to avoid waiting on slow network connections or
        if you don't like to get the related warnings.

    iterative : bool, optional
        Defines whether iterative parsing should be used. It helps reduce
        memory usage at almost the same parsing speed. Default is
        :py:const:`True`.

    use_index : bool, optional
        Defines whether an index of byte offsets needs to be created for
        spectrum elements. Default is :py:const:`False`.

    Returns
    -------
    out : iterator
       An iterator over the dicts with spectrum properties.
    """

    return MzXML(
        source, read_schema=read_schema, iterative=iterative,
        use_index=use_index)


def iterfind(source, path, **kwargs):
    """Parse `source` and yield info on elements with specified local
    name or by specified "XPath".

    .. note:: This function is provided for backward compatibility only.
        If you do multiple :py:func:`iterfind` calls on one file, you should
        create an :py:class:`MzXML` object and use its
        :py:meth:`!iterfind` method.

    Parameters
    ----------
    source : str or file
        File name or file-like object.

    path : str
        Element name or XPath-like expression. Only local names separated
        with slashes are accepted. An asterisk (`*`) means any element.
        You can specify a single condition in the end, such as:
        ``"/path/to/element[some_value>1.5]"``
        Note: you can do much more powerful filtering using plain Python.
        The path can be absolute or "free". Please don't specify
        namespaces.

    recursive : bool, optional
        If :py:const:`False`, subelements will not be processed when
        extracting info from elements. Default is :py:const:`True`.

    iterative : bool, optional
        Specifies whether iterative XML parsing should be used. Iterative
        parsing significantly reduces memory usage and may be just a little
        slower. When `retrieve_refs` is :py:const:`True`, however, it is
        highly recommended to disable iterative parsing if possible.
        Default value is :py:const:`True`.

    read_schema : bool, optional
        If :py:const:`True`, attempt to extract information from the XML schema
        mentioned in the mzIdentML header (default). Otherwise, use default
        parameters. Disable this to avoid waiting on slow network connections or
        if you don't like to get the related warnings.

    Returns
    -------
    out : iterator
    """
    return MzXML(source, **kwargs).iterfind(path, **kwargs)

version_info = xml._make_version_info(MzXML)

chain = aux._make_chain(read, 'read')