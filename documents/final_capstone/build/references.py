"""IEEE-style reference strings. Each entry was checked against a publisher, PubMed/PMC, ACL Anthology, arXiv, PMLR or
proceedings listing (October 2026). Only references cited in the report are printed; numbering follows first citation."""

REFS = {
    "dentex": "I. E. Hamamci et al., “DENTEX: An abnormal tooth detection with dental enumeration and diagnosis benchmark for "
              "panoramic X-rays,” arXiv preprint arXiv:2305.19112, 2023.",
    "hierdet": "I. E. Hamamci, S. Er, E. Simsar, A. Sekuboyina, M. Gundogar, B. Stadlinger, A. Mehl, and B. Menze, "
               "“Diffusion-based hierarchical multi-label object detection to analyze panoramic dental X-rays,” in Proc. Medical "
               "Image Computing and Computer Assisted Intervention (MICCAI), LNCS, vol. 14225. Cham, Switzerland: Springer, 2023, "
               "pp. 389–399, doi: 10.1007/978-3-031-43987-2_38.",
    "schwendicke2019": "F. Schwendicke, T. Golla, M. Dreher, and J. Krois, “Convolutional neural networks for dental image "
                       "diagnostics: A scoping review,” Journal of Dentistry, vol. 91, Art. no. 103226, 2019, "
                       "doi: 10.1016/j.jdent.2019.103226.",
    "lee2018": "J.-H. Lee, D.-H. Kim, S.-N. Jeong, and S.-H. Choi, “Detection and diagnosis of dental caries using a deep "
               "learning-based convolutional neural network algorithm,” Journal of Dentistry, vol. 77, pp. 106–111, 2018, "
               "doi: 10.1016/j.jdent.2018.07.015.",
    "tuzoff2019": "D. V. Tuzoff et al., “Tooth detection and numbering in panoramic radiographs using convolutional neural "
                  "networks,” Dentomaxillofacial Radiology, vol. 48, no. 4, Art. no. 20180051, 2019.",
    "chen2019": "H. Chen, K. Zhang, P. Lyu, H. Li, L. Zhang, J. Wu, and C.-H. Lee, “A deep learning approach to automatic teeth "
                "detection and numbering based on object detection in dental periapical films,” Scientific Reports, vol. 9, "
                "Art. no. 3840, 2019, doi: 10.1038/s41598-019-40414-y.",
    "ekert2019": "T. Ekert, J. Krois, L. Meinhold, K. Elhennawy, R. Emara, T. Golla, and F. Schwendicke, “Deep learning for the "
                 "radiographic detection of apical lesions,” Journal of Endodontics, vol. 45, no. 7, pp. 917–922, 2019.",
    "ren2015": "S. Ren, K. He, R. Girshick, and J. Sun, “Faster R-CNN: Towards real-time object detection with region proposal "
               "networks,” in Advances in Neural Information Processing Systems (NeurIPS), vol. 28, 2015.",
    "he2017mask": "K. He, G. Gkioxari, P. Dollár, and R. Girshick, “Mask R-CNN,” in Proc. IEEE International Conference on "
                  "Computer Vision (ICCV), 2017, pp. 2961–2969.",
    "he2016": "K. He, X. Zhang, S. Ren, and J. Sun, “Deep residual learning for image recognition,” in Proc. IEEE Conference on "
              "Computer Vision and Pattern Recognition (CVPR), 2016, pp. 770–778.",
    "lin2017fpn": "T.-Y. Lin, P. Dollár, R. Girshick, K. He, B. Hariharan, and S. Belongie, “Feature pyramid networks for object "
                  "detection,” in Proc. IEEE Conference on Computer Vision and Pattern Recognition (CVPR), 2017, pp. 2117–2125.",
    "deng2009": "J. Deng, W. Dong, R. Socher, L.-J. Li, K. Li, and L. Fei-Fei, “ImageNet: A large-scale hierarchical image "
                "database,” in Proc. IEEE Conference on Computer Vision and Pattern Recognition (CVPR), 2009, pp. 248–255.",
    "lin2014coco": "T.-Y. Lin et al., “Microsoft COCO: Common objects in context,” in Proc. European Conference on Computer Vision "
                   "(ECCV), LNCS, vol. 8693, 2014, pp. 740–755.",
    "lin2017focal": "T.-Y. Lin, P. Goyal, R. Girshick, K. He, and P. Dollár, “Focal loss for dense object detection,” in Proc. "
                    "IEEE International Conference on Computer Vision (ICCV), 2017, pp. 2980–2988.",
    "guo2017": "C. Guo, G. Pleiss, Y. Sun, and K. Q. Weinberger, “On calibration of modern neural networks,” in Proc. 34th "
               "International Conference on Machine Learning (ICML), PMLR, vol. 70, 2017, pp. 1321–1330.",
    "wang2019": "G. Wang, W. Li, M. Aertsen, J. Deprest, S. Ourselin, and T. Vercauteren, “Aleatoric uncertainty estimation with "
                "test-time augmentation for medical image segmentation with convolutional neural networks,” Neurocomputing, "
                "vol. 335, pp. 34–45, 2019, doi: 10.1016/j.neucom.2019.01.103.",
    "kaufman2012": "S. Kaufman, S. Rosset, C. Perlich, and O. Stitelman, “Leakage in data mining: Formulation, detection, and "
                   "avoidance,” ACM Transactions on Knowledge Discovery from Data, vol. 6, no. 4, Art. no. 15, 2012, "
                   "doi: 10.1145/2382577.2382579.",
    "settles2009": "B. Settles, “Active learning literature survey,” Computer Sciences Technical Report 1648, University of "
                   "Wisconsin–Madison, 2009.",
    "selvaraju2017": "R. R. Selvaraju, M. Cogswell, A. Das, R. Vedantam, D. Parikh, and D. Batra, “Grad-CAM: Visual explanations "
                     "from deep networks via gradient-based localization,” in Proc. IEEE International Conference on Computer "
                     "Vision (ICCV), 2017.",
    "paszke2019": "A. Paszke et al., “PyTorch: An imperative style, high-performance deep learning library,” in Advances in Neural "
                  "Information Processing Systems (NeurIPS), vol. 32, 2019.",
    "vaswani2017": "A. Vaswani et al., “Attention is all you need,” in Advances in Neural Information Processing Systems "
                   "(NeurIPS), vol. 30, 2017.",
    "brown2020": "T. B. Brown et al., “Language models are few-shot learners,” in Advances in Neural Information Processing "
                 "Systems (NeurIPS), vol. 33, 2020.",
    "goodfellow2014": "I. Goodfellow et al., “Generative adversarial nets,” in Advances in Neural Information Processing Systems "
                      "(NeurIPS), vol. 27, 2014.",
    "ho2020": "J. Ho, A. Jain, and P. Abbeel, “Denoising diffusion probabilistic models,” in Advances in Neural Information "
              "Processing Systems (NeurIPS), vol. 33, 2020.",
    "lewis2020": "P. Lewis et al., “Retrieval-augmented generation for knowledge-intensive NLP tasks,” in Advances in Neural "
                 "Information Processing Systems (NeurIPS), vol. 33, 2020.",
    "jing2018": "B. Jing, P. Xie, and E. Xing, “On the automatic generation of medical imaging reports,” in Proc. 56th Annual "
                "Meeting of the Association for Computational Linguistics (ACL), 2018, pp. 2577–2586, doi: 10.18653/v1/P18-1240.",
    "stephan2024": "D. Stephan, A. Bertsch, M. Burwinkel, S. Vinayahalingam, B. Al-Nawas, P. W. Kämmerer, and D. G. E. Thiem, "
                   "“AI in dental radiology—Improving the efficiency of reporting with ChatGPT: Comparative study,” Journal of "
                   "Medical Internet Research, vol. 26, Art. no. e60684, 2024.",
    "iso3950": "International Organization for Standardization, ISO 3950:2016, Dentistry — Designation system for teeth and areas "
               "of the oral cavity. Geneva, Switzerland: ISO, 2016.",
    "youden1950": "W. J. Youden, “Index for rating diagnostic tests,” Cancer, vol. 3, no. 1, pp. 32–35, 1950.",
    "buda2018": "M. Buda, A. Maki, and M. A. Mazurowski, “A systematic study of the class imbalance problem in convolutional "
                "neural networks,” Neural Networks, vol. 106, pp. 249–259, 2018, doi: 10.1016/j.neunet.2018.07.011.",
    "loshchilov2019": "I. Loshchilov and F. Hutter, “Decoupled weight decay regularization,” in Proc. International Conference "
                      "on Learning Representations (ICLR), 2019.",
    "varoquaux2022": "G. Varoquaux and V. Cheplygina, “Machine learning for medical imaging: Methodological failures and "
                     "recommendations for the future,” npj Digital Medicine, vol. 5, Art. no. 48, 2022, doi: 10.1038/s41746-022-00592-y.",
}
