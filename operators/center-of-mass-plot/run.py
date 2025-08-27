import io
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
from distiller_streaming.models import COM

from interactem.core.logger import get_logger
from interactem.core.models.messages import BytesMessage, MessageHeader, MessageSubject
from interactem.operators.operator import operator

logger = get_logger()

@operator
def com_plot(
    inputs: BytesMessage | None, parameters: dict[str, Any]
) -> BytesMessage | None:
    """Plots the center of mass for a scan.
    Parameters:
        xy_rtheta: str, either 'xy' or 'rtheta'
            - 'xy'     → COM_x and COM_y heatmaps
            - 'rtheta' → COM radius and angle heatmaps
    """
    if not inputs:
        logger.warning("No input provided to com_plot")
        return None

    com = COM.from_bytes_message(inputs)
    scan_num = com.header.scan_number

    # Parameter: which plot to make
    mode = parameters.get("xy_rtheta", "xy")
    fig, ax = plt.subplots(1, 2, sharex=True, sharey=True)

    com_mean = np.mean(com.array, axis=(1, 2))
    if mode == "xy":
        # COM_x and COM_y heatmaps
        com_std = np.std(com.array, axis=(1, 2))

        ax[0].imshow(
            com.array[0],
            cmap="bwr",
            vmin=com_mean[0] - com_std[0],
            vmax=com_mean[0] + com_std[0],
            interpolation="none",
        )
        ax[1].imshow(
            com.array[1],
            cmap="bwr",
            vmin=com_mean[1] - com_std[1],
            vmax=com_mean[1] + com_std[1],
            interpolation="none",
        )
        ax[0].set(title="COM_x")
        ax[1].set(title="COM_y")

    elif mode == "rtheta":
        # Radius and angle heatmaps
        com_r = np.sqrt(
            (com.array[0] - com_mean[0]) ** 2 + (com.array[1] - com_mean[1]) ** 2
        )
        com_theta = np.arctan2(
            (com.array[1] - com_mean[1]), (com.array[0] - com_mean[0])
        )

        ax[0].imshow(
            com_r,
            cmap="magma",
            vmin=com_r[10:-10, 10:-10].min(),
            vmax=com_r[10:-10, 10:-10].max(),
            interpolation="none",
        )
        ax[1].imshow(com_theta, cmap="twilight", interpolation="none")
        ax[0].set(title="COM_r")
        ax[1].set(title="COM_theta")

    fig.suptitle(f"scan {scan_num}")

    # Save plot to PNG in memory
    bio = io.BytesIO()
    fig.savefig(bio, format="JPEG", bbox_inches="tight")
    plt.close(fig)
    bio.seek(0)

    return BytesMessage(
        header=MessageHeader(subject=MessageSubject.BYTES, meta={"plot_type": mode}),
        data=bio.getvalue(),
    )
