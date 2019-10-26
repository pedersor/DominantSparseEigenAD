"""
    Several different approaches of computing the fidelity susceptibility chi_F(g)
of 1D TFIM.
"""
import numpy as np
import torch
from TFIM import TFIM

def chiF_perturbation(model):
    """
        Compute chi_F using the full spectrum perturbation formula:
    chi_F = \sum_{n \neq 0} \frac{ |<psi_n(g)| \partial H / \partial g |psi_0(g)>|^2 }
                                 {(E_0(g) - E_n(g))^2}
    """
    Es, psis = torch.symeig(model.Hmatrix, eigenvectors=True)
    psi0 = psis[:, 0]

    model.setpHpg()
    numerators = psi0.matmul(model.pHpgmatrix).matmul(psis)[1:] ** 2
    denominators = (Es[0] - Es[1:]) ** 2
    chiF = (numerators / denominators).sum().item()
    return chiF

def chiF_matrixAD(model, k):
    """
        Compute chi_F using the DominantSymeig primitive, where the matrix to be
    diagonalized is represented as the normal form of a torch.Tensor.
    """
    from DominantSparseEigenAD.Lanczos import DominantSymeig
    dominant_symeig = DominantSymeig.apply
    E0, psi0 = dominant_symeig(model.Hmatrix, k)
    logF = torch.log(psi0.detach().matmul(psi0))
    dlogF, = torch.autograd.grad(logF, model.g, create_graph=True)
    d2logF, = torch.autograd.grad(dlogF, model.g)
    chiF = -d2logF.item()
    return chiF

def chiF_sparseAD(model, k):
    """
        Compute chi_F using the DominantSparseSymeig primitive, where the matrix 
    to be diagonalized is "sparse" and represented as a function.
    """
    import DominantSparseEigenAD.Lanczos as lanczos
    lanczos.setDominantSparseSymeig(model.H, model.Hadjoint_to_gadjoint)
    dominant_sparse_symeig = lanczos.DominantSparseSymeig.apply
    E0, psi0 = dominant_sparse_symeig(model.g, k, model.dim)
    logF = torch.log(psi0.detach().matmul(psi0))
    dlogF, = torch.autograd.grad(logF, model.g, create_graph=True)
    d2logF, = torch.autograd.grad(dlogF, model.g)
    chiF = -d2logF.item()
    return E0, psi0, chiF

def chiF_geometric(model, E0, psi0):
    """
        Compute chi_F using the "geometric" formula:
    chi_F = <\partial psi_0(g) / \partial g | \partial psi_0(g) / \partial g>
        The 1st derivative |\partial psi_0(g) / \partial g> is computed by manually
    implementing a forward AD process.
    """
    from DominantSparseEigenAD.CG import CGSubspaceSparse
    b = -model.pHpg(psi0)
    b = b - torch.matmul(psi0, b) * psi0
    cg = CGSubspaceSparse.apply
    dpsi0 = cg(model.g, E0, b, psi0)
    chiF = torch.matmul(dpsi0, dpsi0).item()
    return chiF

if __name__ == "__main__":
    N = 10
    model = TFIM(N)
    k = 300
    Npoints = 100
    gs = np.linspace(0.45, 1.6, num=Npoints)
    chiFs_perturbation = np.empty(Npoints)
    chiFs_matrixAD = np.empty(Npoints)
    chiFs_sparseAD = np.empty(Npoints)
    chiFs_geometric = np.empty(Npoints)
    for i in range(Npoints):
        model.g = torch.Tensor([gs[i]]).to(torch.float64)
        model.g.requires_grad_(True)

        model.setHmatrix()
        chiFs_perturbation[i] = chiF_perturbation(model)

        chiFs_matrixAD[i] = chiF_matrixAD(model, k)

        E0, psi0, chiFs_sparseAD[i] = chiF_sparseAD(model, k)

        chiFs_geometric[i] = chiF_geometric(model, E0, psi0)

        print("g: ", gs[i], 
                "chiF_perturbation: ", chiFs_perturbation[i], 
                "chiF_matrixAD: ", chiFs_matrixAD[i], 
                "chiF_sparseAD: ", chiFs_sparseAD[i], 
                "chiF_geometric: ", chiFs_geometric[i])
    import matplotlib.pyplot as plt
    plt.plot(gs, chiFs_perturbation, label="perturbation")
    plt.plot(gs, chiFs_matrixAD, label="AD: normal representation")
    plt.plot(gs, chiFs_sparseAD, label="AD: sparse representation")
    plt.plot(gs, chiFs_geometric, label="Forward AD")
    plt.legend()
    plt.xlabel("$g$")
    plt.ylabel("$\\chi_F$")
    plt.title("Fidelity susceptibility of 1D TFIM\n" \
            "$H = - \\sum_{i=0}^{N-1} (g\\sigma_i^x + \\sigma_i^z \\sigma_{i+1}^z)$\n" \
            "$N=%d$" % model.N)
    plt.show()
