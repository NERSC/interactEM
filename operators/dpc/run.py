import io
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import stempy.image as stim
from distiller_streaming.models import COM
from matplotlib.colors import LogNorm

from interactem.core.logger import get_logger
from interactem.core.models.messages import BytesMessage, MessageHeader, MessageSubject
from interactem.operators.operator import operator

logger = get_logger()


FlatScanIdx = int



@operator
def dpc(
    inputs: BytesMessage | None, parameters: dict[str, Any]
) -> BytesMessage | None:
    if not inputs:
        logger.warning("No input provided to com_plot")
        return None

    com = COM.from_bytes_message(inputs)
    scan_num = com.header.scan_number

    flip = parameters.get("flip", True)
    theta = parameters.get("theta", -9)  # rotation between diffraction and real space scan directions
    reg = parameters.get("reg", .1)  # regularization parameter
    theta = theta * np.pi / 180

    ph = stim.phase_from_com(com.array, flip=flip, theta=theta, reg=reg)

    fig, ax = plt.subplots(1, 2, figsize=(10,5))
    ax[0].imshow(ph,vmin=ph[10:-10,].min(),vmax=ph[10:-10,].max())
    ax[0].set(title='DPC')
    plt.suptitle(f'Scan #{scan_num}')
    fig.tight_layout()
    ax[1].imshow(np.abs(np.fft.fftshift(np.fft.fft2(ph))),norm=LogNorm(vmin=1))
    ax[1].set(title='FFT of DPC')
    fig.tight_layout()

    # Save plot to JPEG in memory
    bio = io.BytesIO()
    fig.savefig(bio, format="JPEG", bbox_inches="tight")
    plt.close(fig)
    bio.seek(0)

    return BytesMessage(
        header=MessageHeader(subject=MessageSubject.BYTES),
        data=bio.getvalue(),
    )
